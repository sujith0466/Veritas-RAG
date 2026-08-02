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
from backend.modules.embedding.events.payloads import (
    EVENT_EMBEDDING_FAILED,
    EVENT_EMBEDDING_STARTED,
    EmbeddingDomainEvent,
)
from backend.modules.embedding.models.embedding_job import EmbeddingJob
from backend.modules.embedding.providers.base import EmbeddingBatchResult
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

    async def test_process_batch_idempotency_filtering(self) -> None:
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
        # Repository reports h_cached_1 and h_cached_2 already exist in vector storage
        mock_repo.filter_existing_content_hashes.return_value = {"h_cached_1", "h_cached_2"}

        mock_dispatcher = AsyncMock(spec=EventDispatcher)
        service = EmbeddingService(repository=mock_repo, event_dispatcher=mock_dispatcher)

        mock_repo.update_job_progress.return_value = job
        completed = await service.process_embedding_batch(job_id=job_id, tenant_id="t1", batch_size=100)

        # Verify cached chunks were marked as embedded directly without vector computation
        assert mock_repo.mark_chunks_as_embedded.await_count == 2
        mock_repo.bulk_insert_chunk_embeddings.assert_awaited_once()
        inserted_recs = mock_repo.bulk_insert_chunk_embeddings.call_args[0][0]
        assert len(inserted_recs) == 2
        assert {r.content_hash for r in inserted_recs} == {"h_missing_1", "h_missing_2"}

        # Verify progress and completion events published
        assert mock_dispatcher.publish.await_count >= 2
        event_types = [call[0][0].event_type for call in mock_dispatcher.publish.call_args_list]
        assert EventType.EMBEDDING_PROGRESS in event_types
        assert EventType.EMBEDDING_COMPLETED in event_types

    async def test_process_batch_failure_publishes_event_and_updates_job(self) -> None:
        class FailingProvider(LocalEmbeddingProvider):
            def __init__(self, **kwargs: Any) -> None:
                super().__init__(model_name="BAAI/bge-small-en-v1.5", offline=True)

            async def embed_documents(self, texts: list[str]) -> EmbeddingBatchResult:
                raise ProviderTimeoutError("Simulated provider timeout")

        register_provider("failing", FailingProvider)

        mock_repo = AsyncMock()
        job = EmbeddingJob(
            id=uuid.uuid4(),
            tenant_id="t1",
            document_id=uuid.uuid4(),
            document_version_id=uuid.uuid4(),
            provider="failing",
            model_name="m",
            status="PROCESSING",
        )
        mock_repo.get_job_by_id_and_tenant.return_value = job
        mock_repo.get_unembedded_chunks.return_value = [
            DocumentChunk(id=uuid.uuid4(), tenant_id="t1", document_version_id=job.document_version_id, content="fail", content_hash="hf")
        ]
        mock_repo.filter_existing_content_hashes.return_value = set()

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
