"""Unit tests for Phase 2 Milestone 2: Embedding Pipeline (Milestone D - Service Layer).

Verifies `EmbeddingService` job initiation, token quota verification, zero-call idempotency
filtering (`cached_chunks vs missing_chunks`), batch vectorization, and domain event publishing.
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from backend.core.events.dispatcher import EventDispatcher
from backend.core.events.types import EventType
from backend.modules.chunking.models.chunk import DocumentChunk
from backend.modules.embedding.models.chunk_embedding import ChunkEmbedding
from backend.modules.embedding.events.payloads import (
    EVENT_EMBEDDING_FAILED,
    EVENT_EMBEDDING_STARTED,
    EmbeddingDomainEvent,
)
from backend.modules.embedding.models.embedding_job import EmbeddingJob
from backend.modules.embedding.providers.factory import register_provider
from backend.modules.embedding.providers.local_provider import LocalEmbeddingProvider
from backend.modules.embedding.schemas.errors import (
    InvalidInputError,
    ProviderTimeoutError,
    TokenQuotaExceededError,
)
from backend.modules.embedding.services.embedding_service import EmbeddingService


class MockOfflineProvider(LocalEmbeddingProvider):
    """Deterministic local provider guaranteed to stay offline during unit testing."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(model_name="BAAI/bge-small-en-v1.5", offline=True)


@pytest.fixture(autouse=True)
def register_mock_offline_provider() -> None:
    register_provider("openai", MockOfflineProvider)
    register_provider("cohere", MockOfflineProvider)
    register_provider("local", MockOfflineProvider)


@pytest.mark.asyncio
class TestEmbeddingService:
    """Test suite verifying `EmbeddingService` orchestration and idempotency rules."""

    async def test_initiate_job_success(self) -> None:
        mock_repo = AsyncMock()
        doc_ver = uuid.uuid4()
        mock_repo.get_unembedded_chunks.return_value = [
            DocumentChunk(id=uuid.uuid4(), tenant_id="t1", document_version_id=doc_ver, content="c1", content_hash="h1"),
            DocumentChunk(id=uuid.uuid4(), tenant_id="t1", document_version_id=doc_ver, content="c2", content_hash="h2"),
        ]
        mock_repo.get_tenant_metrics.return_value = {"total_tokens_consumed": 1000}

        def mock_create(job: EmbeddingJob) -> EmbeddingJob:
            job.id = uuid.uuid4()
            return job

        mock_repo.create_job.side_effect = mock_create

        mock_dispatcher = AsyncMock(spec=EventDispatcher)
        service = EmbeddingService(repository=mock_repo, event_dispatcher=mock_dispatcher)

        job = await service.initiate_embedding_job(
            tenant_id="t1",
            document_id=uuid.uuid4(),
            document_version_id=doc_ver,
            provider="local",
            max_token_quota=50000,
        )

        assert job.status == "PENDING"
        assert job.total_chunks == 2
        mock_repo.create_job.assert_awaited_once()
        mock_dispatcher.publish.assert_awaited_once()
        published_event = mock_dispatcher.publish.call_args[0][0]
        assert isinstance(published_event, EmbeddingDomainEvent)
        assert published_event.event_type == EventType.EMBEDDING_STARTED
        assert published_event.payload is not None
        assert published_event.payload.event_type == EVENT_EMBEDDING_STARTED

    async def test_initiate_job_no_chunks_raises_invalid_input(self) -> None:
        mock_repo = AsyncMock()
        mock_repo.get_unembedded_chunks.return_value = []
        service = EmbeddingService(repository=mock_repo)

        with pytest.raises(InvalidInputError):
            await service.initiate_embedding_job(
                tenant_id="t1",
                document_id=uuid.uuid4(),
                document_version_id=uuid.uuid4(),
            )

    async def test_initiate_job_token_quota_exceeded(self) -> None:
        mock_repo = AsyncMock()
        mock_repo.get_unembedded_chunks.return_value = [MagicMock()]
        mock_repo.get_tenant_metrics.return_value = {"total_tokens_consumed": 50000}
        service = EmbeddingService(repository=mock_repo)

        with pytest.raises(TokenQuotaExceededError):
            await service.initiate_embedding_job(
                tenant_id="t1",
                document_id=uuid.uuid4(),
                document_version_id=uuid.uuid4(),
                max_token_quota=50000,
            )

    from unittest.mock import patch

    from backend.modules.embedding.models.chunk_embedding import ChunkEmbedding

    @patch("backend.cache.rate_limit.RateLimiter.check_limit", return_value={"current": 1, "limit": 600, "remaining": 599})
    async def test_process_batch_idempotency_filtering(self, mock_rate_limit) -> None:
        mock_repo = AsyncMock()
        job_id = uuid.uuid4()
        doc_ver = uuid.uuid4()
        job = EmbeddingJob(
            id=job_id,
            tenant_id="t1",
            document_id=uuid.uuid4(),
            document_version_id=doc_ver,
            provider="local",
            model_name="BAAI/bge-small-en-v1.5",
            total_chunks=4,
            processed_chunks=0,
            status="PENDING",
        )
        mock_repo.get_job_by_id_and_tenant.return_value = job

        c1 = DocumentChunk(id=uuid.uuid4(), tenant_id="t1", document_version_id=doc_ver, content="cached 1", content_hash="h_cached_1")
        c2 = DocumentChunk(id=uuid.uuid4(), tenant_id="t1", document_version_id=doc_ver, content="cached 2", content_hash="h_cached_2")
        c3 = DocumentChunk(id=uuid.uuid4(), tenant_id="t1", document_version_id=doc_ver, content="missing 1", content_hash="h_missing_1")
        c4 = DocumentChunk(id=uuid.uuid4(), tenant_id="t1", document_version_id=doc_ver, content="missing 2", content_hash="h_missing_2")

        # First call returns 4 unindexed chunks, second call returns [] to terminate loop
        mock_repo.get_unembedded_chunks.side_effect = [[c1, c2, c3, c4], []]
        # Repository reports existing embeddings for h_cached_1 and h_cached_2
        mock_repo.get_existing_embeddings_by_hashes.return_value = {
            "h_cached_1": ChunkEmbedding(
                id=uuid.uuid4(),
                tenant_id="t1",
                chunk_id=uuid.uuid4(),
                document_version_id=uuid.uuid4(),
                content_hash="h_cached_1",
                provider="local",
                model_name="BAAI/bge-small-en-v1.5",
                dimension=384,
                embedding_vector=[0.1] * 384,
            ),
            "h_cached_2": ChunkEmbedding(
                id=uuid.uuid4(),
                tenant_id="t1",
                chunk_id=uuid.uuid4(),
                document_version_id=uuid.uuid4(),
                content_hash="h_cached_2",
                provider="local",
                model_name="BAAI/bge-small-en-v1.5",
                dimension=384,
                embedding_vector=[0.2] * 384,
            ),
        }

        mock_dispatcher = AsyncMock(spec=EventDispatcher)
        service = EmbeddingService(repository=mock_repo, event_dispatcher=mock_dispatcher)

        mock_repo.update_job_progress.return_value = job
        completed = await service.process_embedding_batch(job_id=job_id, tenant_id="t1", batch_size=100)

        # Verify cached chunks were marked as embedded directly
        assert mock_repo.mark_chunks_as_embedded.await_count == 2
        # Verify bulk_insert_chunk_embeddings was called for BOTH cached chunks and missing chunks
        assert mock_repo.bulk_insert_chunk_embeddings.await_count == 2
        
        # Call 1: cached chunks insertion bound to CURRENT document version id
        cached_call_recs = mock_repo.bulk_insert_chunk_embeddings.call_args_list[0][0][0]
        assert len(cached_call_recs) == 2
        assert {r.chunk_id for r in cached_call_recs} == {c1.id, c2.id}
        assert all(r.document_version_id == doc_ver for r in cached_call_recs)
        assert all(r.dimension == 384 for r in cached_call_recs)

        # Call 2: missing chunks insertion bound to CURRENT document version id
        missing_call_recs = mock_repo.bulk_insert_chunk_embeddings.call_args_list[1][0][0]
        assert len(missing_call_recs) == 2
        assert {r.content_hash for r in missing_call_recs} == {"h_missing_1", "h_missing_2"}
        assert all(r.document_version_id == doc_ver for r in missing_call_recs)

        # Verify progress and completion events published
        assert mock_dispatcher.publish.await_count >= 2
        event_types = [call[0][0].event_type for call in mock_dispatcher.publish.call_args_list]
        assert EventType.EMBEDDING_PROGRESS in event_types
        assert EventType.EMBEDDING_COMPLETED in event_types

    @patch("backend.cache.rate_limit.RateLimiter.check_limit", return_value={"current": 1, "limit": 600, "remaining": 599})
    async def test_process_batch_fully_cached_version(self, mock_rate_limit) -> None:
        """Verify 100% cached version makes zero provider calls and stages all embeddings."""
        mock_repo = AsyncMock()
        job_id = uuid.uuid4()
        doc_ver = uuid.uuid4()
        job = EmbeddingJob(
            id=job_id,
            tenant_id="t1",
            document_id=uuid.uuid4(),
            document_version_id=doc_ver,
            provider="local",
            model_name="BAAI/bge-small-en-v1.5",
            total_chunks=2,
            processed_chunks=0,
            status="PENDING",
        )
        mock_repo.get_job_by_id_and_tenant.return_value = job

        c1 = DocumentChunk(id=uuid.uuid4(), tenant_id="t1", document_version_id=doc_ver, content="cached 1", content_hash="h1")
        c2 = DocumentChunk(id=uuid.uuid4(), tenant_id="t1", document_version_id=doc_ver, content="cached 2", content_hash="h2")

        mock_repo.get_unembedded_chunks.side_effect = [[c1, c2], []]
        mock_repo.get_existing_embeddings_by_hashes.return_value = {
            "h1": ChunkEmbedding(
                id=uuid.uuid4(),
                tenant_id="t1",
                chunk_id=uuid.uuid4(),
                document_version_id=uuid.uuid4(),
                content_hash="h1",
                provider="local",
                model_name="BAAI/bge-small-en-v1.5",
                dimension=384,
                embedding_vector=[0.1] * 384,
            ),
            "h2": ChunkEmbedding(
                id=uuid.uuid4(),
                tenant_id="t1",
                chunk_id=uuid.uuid4(),
                document_version_id=uuid.uuid4(),
                content_hash="h2",
                provider="local",
                model_name="BAAI/bge-small-en-v1.5",
                dimension=384,
                embedding_vector=[0.2] * 384,
            ),
        }

        mock_dispatcher = AsyncMock(spec=EventDispatcher)
        service = EmbeddingService(repository=mock_repo, event_dispatcher=mock_dispatcher)

        mock_repo.update_job_progress.return_value = job
        await service.process_embedding_batch(job_id=job_id, tenant_id="t1", batch_size=100)

        # Bulk insert called exactly once for cached records
        mock_repo.bulk_insert_chunk_embeddings.assert_awaited_once()
        staged_recs = mock_repo.bulk_insert_chunk_embeddings.call_args[0][0]
        assert len(staged_recs) == 2
        assert {r.chunk_id for r in staged_recs} == {c1.id, c2.id}
        assert all(r.document_version_id == doc_ver for r in staged_recs)

        # Mark chunks embedded called once
        mock_repo.mark_chunks_as_embedded.assert_awaited_once_with([c1.id, c2.id], "t1")
        # Job progress incremented by 2
        mock_repo.update_job_progress.assert_any_await(job_id, "t1", processed_delta=2)

    @patch("backend.cache.rate_limit.RateLimiter.check_limit", return_value={"current": 1, "limit": 600, "remaining": 599})
    async def test_process_batch_duplicate_content_hashes_in_document(self, mock_rate_limit) -> None:
        """Verify duplicate content hashes in the same version receive distinct ChunkEmbedding records."""
        mock_repo = AsyncMock()
        job_id = uuid.uuid4()
        doc_ver = uuid.uuid4()
        job = EmbeddingJob(
            id=job_id,
            tenant_id="t1",
            document_id=uuid.uuid4(),
            document_version_id=doc_ver,
            provider="local",
            model_name="BAAI/bge-small-en-v1.5",
            total_chunks=2,
            processed_chunks=0,
            status="PENDING",
        )
        mock_repo.get_job_by_id_and_tenant.return_value = job

        # Both chunks have identical content_hash "duplicate_hash"
        c1 = DocumentChunk(id=uuid.uuid4(), tenant_id="t1", document_version_id=doc_ver, content="dup", content_hash="duplicate_hash")
        c2 = DocumentChunk(id=uuid.uuid4(), tenant_id="t1", document_version_id=doc_ver, content="dup", content_hash="duplicate_hash")

        mock_repo.get_unembedded_chunks.side_effect = [[c1, c2], []]
        mock_repo.get_existing_embeddings_by_hashes.return_value = {
            "duplicate_hash": ChunkEmbedding(
                id=uuid.uuid4(),
                tenant_id="t1",
                chunk_id=uuid.uuid4(),
                document_version_id=uuid.uuid4(),
                content_hash="duplicate_hash",
                provider="local",
                model_name="BAAI/bge-small-en-v1.5",
                dimension=384,
                embedding_vector=[0.5] * 384,
            ),
        }

        mock_dispatcher = AsyncMock(spec=EventDispatcher)
        service = EmbeddingService(repository=mock_repo, event_dispatcher=mock_dispatcher)

        mock_repo.update_job_progress.return_value = job
        await service.process_embedding_batch(job_id=job_id, tenant_id="t1", batch_size=100)

        # 1 cache hit generates 2 separate ChunkEmbedding records, each with its chunk's unique id
        staged_recs = mock_repo.bulk_insert_chunk_embeddings.call_args[0][0]
        assert len(staged_recs) == 2
        assert staged_recs[0].chunk_id == c1.id
        assert staged_recs[1].chunk_id == c2.id
        assert staged_recs[0].document_version_id == doc_ver
        assert staged_recs[1].document_version_id == doc_ver

    @patch("backend.cache.rate_limit.RateLimiter.check_limit", return_value={"current": 1, "limit": 600, "remaining": 599})
    async def test_process_batch_dimension_mismatch_falls_back_to_provider(self, mock_rate_limit) -> None:
        """Verify cached record with wrong dimension is rejected as cache hit and vectorized by provider."""
        mock_repo = AsyncMock()
        job_id = uuid.uuid4()
        doc_ver = uuid.uuid4()
        job = EmbeddingJob(
            id=job_id,
            tenant_id="t1",
            document_id=uuid.uuid4(),
            document_version_id=doc_ver,
            provider="local",
            model_name="BAAI/bge-small-en-v1.5",
            total_chunks=1,
            processed_chunks=0,
            status="PENDING",
        )
        mock_repo.get_job_by_id_and_tenant.return_value = job

        c1 = DocumentChunk(id=uuid.uuid4(), tenant_id="t1", document_version_id=doc_ver, content="dim mismatch", content_hash="h_bad_dim")
        mock_repo.get_unembedded_chunks.side_effect = [[c1], []]

        # Cached record has dimension 768, but manager expects 384
        mock_repo.get_existing_embeddings_by_hashes.return_value = {
            "h_bad_dim": ChunkEmbedding(
                id=uuid.uuid4(),
                tenant_id="t1",
                chunk_id=uuid.uuid4(),
                document_version_id=uuid.uuid4(),
                content_hash="h_bad_dim",
                provider="local",
                model_name="BAAI/bge-small-en-v1.5",
                dimension=768,
                embedding_vector=[0.1] * 768,
            ),
        }

        mock_dispatcher = AsyncMock(spec=EventDispatcher)
        service = EmbeddingService(repository=mock_repo, event_dispatcher=mock_dispatcher)

        mock_repo.update_job_progress.return_value = job
        await service.process_embedding_batch(job_id=job_id, tenant_id="t1", batch_size=100)

        # Chunks were NOT routed to cache insert; instead routed to provider embedding
        assert mock_repo.bulk_insert_chunk_embeddings.await_count == 1
        inserted_recs = mock_repo.bulk_insert_chunk_embeddings.call_args[0][0]
        assert len(inserted_recs) == 1
        assert inserted_recs[0].chunk_id == c1.id
        # Vector was generated with expected 384 dimension
        assert inserted_recs[0].dimension == 384

    @patch("backend.modules.embedding.services.embedding_service.EmbeddingManager.vectorize_batch")
    @patch("backend.cache.rate_limit.RateLimiter.check_limit", return_value={"current": 1, "limit": 600, "remaining": 599})
    async def test_process_batch_failure_publishes_event_and_updates_job(self, mock_rate_limit, mock_vectorize) -> None:
        mock_vectorize.side_effect = ProviderTimeoutError("Simulated provider timeout")

        mock_repo = AsyncMock()
        job = EmbeddingJob(
            id=uuid.uuid4(),
            tenant_id="t1",
            document_id=uuid.uuid4(),
            document_version_id=uuid.uuid4(),
            provider="local",
            model_name="m",
            status="PROCESSING",
        )
        mock_repo.get_job_by_id_and_tenant.return_value = job
        mock_repo.get_unembedded_chunks.return_value = [
            DocumentChunk(id=uuid.uuid4(), tenant_id="t1", document_version_id=job.document_version_id, content="fail", content_hash="hf")
        ]
        mock_repo.get_existing_embeddings_by_hashes.return_value = {}

        mock_dispatcher = AsyncMock(spec=EventDispatcher)
        service = EmbeddingService(repository=mock_repo, event_dispatcher=mock_dispatcher)

        with pytest.raises(ProviderTimeoutError):
            await service.process_embedding_batch(job_id=job.id, tenant_id="t1")

        mock_repo.update_job_progress.assert_any_await(
            job.id, "t1", failed_delta=1, status="FAILED", error_message="Simulated provider timeout"
        )
        assert mock_dispatcher.publish.await_count == 1
        failed_event = mock_dispatcher.publish.call_args[0][0]
        assert failed_event.event_type == EventType.EMBEDDING_FAILED
        assert failed_event.payload is not None
        assert failed_event.payload.event_type == EVENT_EMBEDDING_FAILED

    async def test_get_status_and_metrics_delegation(self) -> None:
        mock_repo = AsyncMock()
        mock_repo.get_job_by_id_and_tenant.return_value = EmbeddingJob(id=uuid.uuid4(), tenant_id="t1", provider="p", model_name="m")
        mock_repo.get_tenant_metrics.return_value = {"active_jobs_count": 3}
        service = EmbeddingService(repository=mock_repo)

        job = await service.get_job_status(uuid.uuid4(), "t1")
        assert job is not None
        metrics = await service.get_tenant_metrics("t1")
        assert metrics["active_jobs_count"] == 3
