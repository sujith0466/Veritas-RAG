"""Unit tests for Phase 2 Milestone 2: Embedding Pipeline (Milestone B - Database Layer).

Verifies `EmbeddingJob` and `ChunkEmbedding` ORM models and `EmbeddingRepository`
CRUD operations, multi-tenant isolation, and zero-call idempotency engine.
"""

from unittest.mock import AsyncMock, MagicMock
import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.chunking.models.chunk import DocumentChunk
from backend.modules.embedding.models.chunk_embedding import ChunkEmbedding
from backend.modules.embedding.models.embedding_job import EmbeddingJob
from backend.modules.embedding.repositories.embedding_repository import EmbeddingRepository


@pytest.mark.asyncio
class TestEmbeddingRepository:
    """Test suite verifying `EmbeddingRepository` queries, bulk actions, and idempotency filtering."""

    async def test_create_job(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        repo = EmbeddingRepository(mock_session)

        job = EmbeddingJob(
            tenant_id="tenant-1",
            document_id=uuid.uuid4(),
            document_version_id=uuid.uuid4(),
            provider="openai",
            model_name="text-embedding-3-large",
            total_chunks=100,
        )

        created = await repo.create_job(job)
        assert created is job
        mock_session.add.assert_called_once_with(job)
        mock_session.flush.assert_awaited_once()
        mock_session.refresh.assert_awaited_once_with(job)

    async def test_get_job_by_id_and_tenant(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_job = EmbeddingJob(tenant_id="tenant-1", provider="openai", model_name="m", total_chunks=10)
        mock_result.scalar_one_or_none.return_value = mock_job
        mock_session.execute.return_value = mock_result

        repo = EmbeddingRepository(mock_session)
        found = await repo.get_job_by_id_and_tenant(mock_job.id, "tenant-1")

        assert found is mock_job
        mock_session.execute.assert_awaited_once()

    async def test_list_jobs_by_tenant(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        mock_count_res = MagicMock()
        mock_count_res.scalar.return_value = 2

        mock_items_res = MagicMock()
        mock_jobs = [
            EmbeddingJob(tenant_id="tenant-1", provider="openai", model_name="m", total_chunks=10),
            EmbeddingJob(tenant_id="tenant-1", provider="openai", model_name="m", total_chunks=20),
        ]
        mock_items_res.scalars.return_value.all.return_value = mock_jobs

        mock_session.execute.side_effect = [mock_count_res, mock_items_res]

        repo = EmbeddingRepository(mock_session)
        items, total = await repo.list_jobs_by_tenant("tenant-1", status="PROCESSING", skip=0, limit=10)

        assert total == 2
        assert items == mock_jobs
        assert mock_session.execute.await_count == 2

    async def test_update_job_progress(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_job = EmbeddingJob(
            tenant_id="tenant-1",
            provider="openai",
            model_name="m",
            total_chunks=100,
            processed_chunks=10,
            failed_chunks=0,
            total_tokens_consumed=500,
            status="PROCESSING",
        )
        mock_result.scalar_one_or_none.return_value = mock_job
        mock_session.execute.return_value = mock_result

        repo = EmbeddingRepository(mock_session)
        updated = await repo.update_job_progress(
            job_id=mock_job.id,
            tenant_id="tenant-1",
            processed_delta=15,
            failed_delta=2,
            tokens_delta=300,
            status="COMPLETED",
        )

        assert updated is not None
        assert updated.processed_chunks == 25
        assert updated.failed_chunks == 2
        assert updated.total_tokens_consumed == 800
        assert updated.status == "COMPLETED"
        mock_session.flush.assert_awaited_once()
        mock_session.refresh.assert_awaited_once_with(mock_job)

    async def test_get_unembedded_chunks(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        doc_ver = uuid.uuid4()
        mock_chunks = [
            DocumentChunk(tenant_id="tenant-1", document_id=uuid.uuid4(), document_version_id=doc_ver, chunk_index=0, content="c0", content_hash="h0", strategy_used="s"),
            DocumentChunk(tenant_id="tenant-1", document_id=uuid.uuid4(), document_version_id=doc_ver, chunk_index=1, content="c1", content_hash="h1", strategy_used="s"),
        ]
        mock_result.scalars.return_value.all.return_value = mock_chunks
        mock_session.execute.return_value = mock_result

        repo = EmbeddingRepository(mock_session)
        chunks = await repo.get_unembedded_chunks("tenant-1", doc_ver, batch_size=50)

        assert chunks == mock_chunks
        mock_session.execute.assert_awaited_once()

    async def test_filter_existing_content_hashes(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = ["hash_a", "hash_c"]
        mock_session.execute.return_value = mock_result

        repo = EmbeddingRepository(mock_session)
        existing = await repo.filter_existing_content_hashes(
            hashes=["hash_a", "hash_b", "hash_c"],
            tenant_id="tenant-1",
            provider="openai",
            model_name="text-embedding-3-large",
        )

        assert existing == {"hash_a", "hash_c"}
        mock_session.execute.assert_awaited_once()

        # Check empty list shortcut returns set without executing query
        mock_session.execute.reset_mock()
        empty_res = await repo.filter_existing_content_hashes([], "tenant-1", "openai", "text-embedding-3-large")
        assert empty_res == set()
        mock_session.execute.assert_not_called()

    async def test_get_existing_embeddings_by_hashes(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        rec_a = ChunkEmbedding(tenant_id="t-1", chunk_id=uuid.uuid4(), document_version_id=uuid.uuid4(), content_hash="h_a", provider="openai", model_name="m", dimension=1024, embedding_vector=[0.1])
        mock_result.scalars.return_value.all.return_value = [rec_a]
        mock_session.execute.return_value = mock_result

        repo = EmbeddingRepository(mock_session)
        res_map = await repo.get_existing_embeddings_by_hashes(["h_a", "h_b"], "t-1", "openai", "m")

        assert "h_a" in res_map
        assert res_map["h_a"] is rec_a
        assert "h_b" not in res_map

    async def test_bulk_insert_chunk_embeddings(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        repo = EmbeddingRepository(mock_session)

        recs = [
            ChunkEmbedding(tenant_id="t-1", chunk_id=uuid.uuid4(), document_version_id=uuid.uuid4(), content_hash="h_1", provider="openai", model_name="m", dimension=1536, embedding_vector=[0.1] * 1536),
            ChunkEmbedding(tenant_id="t-1", chunk_id=uuid.uuid4(), document_version_id=uuid.uuid4(), content_hash="h_2", provider="openai", model_name="m", dimension=1536, embedding_vector=[0.2] * 1536),
        ]

        count = await repo.bulk_insert_chunk_embeddings(recs)
        assert count == 2
        mock_session.add_all.assert_called_once_with(recs)
        mock_session.flush.assert_awaited_once()

    async def test_mark_chunks_as_embedded(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.rowcount = 3
        mock_session.execute.return_value = mock_result

        repo = EmbeddingRepository(mock_session)
        updated_count = await repo.mark_chunks_as_embedded([uuid.uuid4(), uuid.uuid4(), uuid.uuid4()], "tenant-1")

        assert updated_count == 3
        mock_session.execute.assert_awaited_once()
        mock_session.flush.assert_awaited_once()

    async def test_get_tenant_metrics(self) -> None:
        mock_session = AsyncMock(spec=AsyncSession)
        
        # Mocks for active_jobs, completed_jobs, failed_jobs, total_tokens, total_vectors, provider_distribution
        res_active = MagicMock()
        res_active.scalar.return_value = 1
        res_completed = MagicMock()
        res_completed.scalar.return_value = 4
        res_failed = MagicMock()
        res_failed.scalar.return_value = 0
        res_tokens = MagicMock()
        res_tokens.scalar.return_value = 12500
        res_vectors = MagicMock()
        res_vectors.scalar.return_value = 450
        res_dist = MagicMock()
        res_dist.all.return_value = [("openai", 400), ("cohere", 50)]

        mock_session.execute.side_effect = [res_active, res_completed, res_failed, res_tokens, res_vectors, res_dist]

        repo = EmbeddingRepository(mock_session)
        metrics = await repo.get_tenant_metrics("tenant-1")

        assert metrics["active_jobs_count"] == 1
        assert metrics["completed_jobs_count"] == 4
        assert metrics["failed_jobs_count"] == 0
        assert metrics["total_tokens_consumed"] == 12500
        assert metrics["total_vectors_stored"] == 450
        assert metrics["provider_distribution"] == {"openai": 400, "cohere": 50}
