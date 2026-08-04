"""Unit tests for Vector Storage Service & Celery Worker Layer (`ADR-M3-001`).

Tests `VectorStorageService` orchestration of HNSW index creation, point upserts,
database metadata state transitions (`PENDING -> PROCESSING -> COMPLETED/FAILED`),
domain event publishing (`VectorsIndexed`), and Celery worker retry behavior (`ADR-M3-002`).
"""

from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.events.dispatcher import EventDispatcher
from backend.modules.chunking.models.chunk import DocumentChunk
from backend.modules.embedding.models.chunk_embedding import ChunkEmbedding
from backend.modules.vector.models.vector_metadata import VectorIndexMetadata
from backend.modules.vector.providers import BaseVectorDBProvider
from backend.modules.vector.schemas.errors import (
    QdrantConnectionError,
)
from backend.modules.vector.services.vector_service import VectorStorageService


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def mock_provider() -> AsyncMock:
    provider = AsyncMock(spec=BaseVectorDBProvider)
    provider.provider_name = "qdrant"
    provider.ensure_collection.return_value = True
    provider.create_payload_indexes.return_value = True
    provider.upsert_points.return_value = 2
    provider.delete_points_by_filter.return_value = 5
    return provider


@pytest.fixture
def mock_dispatcher() -> AsyncMock:
    return AsyncMock(spec=EventDispatcher)


@pytest.fixture
def service(mock_session: AsyncMock, mock_provider: AsyncMock, mock_dispatcher: AsyncMock) -> VectorStorageService:
    return VectorStorageService(
        session=mock_session,
        provider=mock_provider,
        dispatcher=mock_dispatcher,
    )


@pytest.mark.unit
@pytest.mark.asyncio
class TestVectorStorageService:
    """Test `VectorStorageService` synchronization workflows and error recovery."""

    async def test_sync_document_vectors_no_embeddings_skips(self, service: VectorStorageService, mock_session: AsyncMock) -> None:
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        count = await service.sync_document_vectors(uuid.uuid4(), uuid.uuid4(), "tenant-1")
        assert count == 0
        service.provider.upsert_points.assert_not_called()

    async def test_sync_document_vectors_success_flow(
        self, service: VectorStorageService, mock_session: AsyncMock, mock_provider: AsyncMock, mock_dispatcher: AsyncMock
    ) -> None:
        doc_id = uuid.uuid4()
        ver_id = uuid.uuid4()
        chunk_id = uuid.uuid4()

        emb = ChunkEmbedding(
            id=uuid.uuid4(),
            tenant_id="tenant-1",
            chunk_id=chunk_id,
            document_version_id=ver_id,
            content_hash="sha-abc",
            provider="openai",
            model_name="text-embedding-3-large",
            dimension=1536,
            embedding_vector=[0.1] * 1536,
        )
        chunk = DocumentChunk(
            id=chunk_id,
            tenant_id="tenant-1",
            document_id=doc_id,
            document_version_id=ver_id,
            chunk_index=0,
            content="Hello world",
            content_hash="sha-abc",
            strategy_used="hierarchical",
            token_count=10,
            character_count=50,
        )
        meta = VectorIndexMetadata(
            id=uuid.uuid4(),
            tenant_id="tenant-1",
            document_id=doc_id,
            document_version_id=ver_id,
            collection_name="raguard_knowledge_1536",
            status="PENDING",
        )

        # Mock execute queries: 1. embeddings, 2. chunks, 3. get_or_create_metadata existing check, 4. update_sync_status check
        mock_emb_res = MagicMock()
        mock_emb_res.scalars.return_value.all.return_value = [emb]

        mock_chunk_res = MagicMock()
        mock_chunk_res.scalars.return_value.all.return_value = [chunk]

        mock_meta_res = MagicMock()
        mock_meta_res.scalar_one_or_none.return_value = meta

        mock_session.execute.side_effect = [
            mock_emb_res,
            mock_chunk_res,
            mock_meta_res,  # get_or_create_metadata
            mock_meta_res,  # cleanup old versions
            mock_meta_res,  # update_sync_status check
            mock_meta_res,  # update_sync_status PROCESSING
            mock_meta_res,  # update_sync_status COMPLETED
            mock_meta_res,
            mock_meta_res,
        ]

        count = await service.sync_document_vectors(doc_id, ver_id, "tenant-1")
        assert count == 2
        mock_provider.ensure_collection.assert_awaited_once()
        mock_provider.create_payload_indexes.assert_awaited_once()
        mock_provider.upsert_points.assert_awaited_once()
        mock_dispatcher.publish.assert_awaited_once()

    async def test_sync_document_vectors_failure_emits_event(
        self, service: VectorStorageService, mock_session: AsyncMock, mock_provider: AsyncMock, mock_dispatcher: AsyncMock
    ) -> None:
        doc_id = uuid.uuid4()
        ver_id = uuid.uuid4()
        emb = ChunkEmbedding(
            id=uuid.uuid4(),
            tenant_id="tenant-1",
            chunk_id=uuid.uuid4(),
            document_version_id=ver_id,
            content_hash="sha-abc",
            provider="openai",
            model_name="text-embedding-3-large",
            dimension=1536,
            embedding_vector=[0.1] * 1536,
        )
        meta = VectorIndexMetadata(
            id=uuid.uuid4(),
            tenant_id="tenant-1",
            document_id=doc_id,
            document_version_id=ver_id,
            collection_name="raguard_knowledge_1536",
            status="PENDING",
        )

        mock_emb_res = MagicMock()
        mock_emb_res.scalars.return_value.all.return_value = [emb]
        mock_chunk_res = MagicMock()
        mock_chunk_res.scalars.return_value.all.return_value = []
        mock_meta_res = MagicMock()
        mock_meta_res.scalar_one_or_none.return_value = meta

        mock_session.execute.side_effect = [
            mock_emb_res,
            mock_chunk_res,
            mock_meta_res,
            mock_meta_res,
            mock_meta_res,
            mock_meta_res,
            mock_meta_res,
            mock_meta_res,
        ]

        mock_provider.upsert_points.side_effect = QdrantConnectionError("Cluster offline")

        with pytest.raises(QdrantConnectionError):
            await service.sync_document_vectors(doc_id, ver_id, "tenant-1")

        mock_dispatcher.publish.assert_awaited_once()
        event = mock_dispatcher.publish.call_args[0][0]
        assert event.payload.event_type == "vector.index_failed"
        assert event.payload.data["error_code"] == "VEC_003"

    async def test_delete_document_points(self, service: VectorStorageService, mock_session: AsyncMock, mock_provider: AsyncMock) -> None:
        doc_id = uuid.uuid4()
        mock_col_res = MagicMock()
        mock_col_res.scalars.return_value.all.return_value = ["raguard_knowledge_1536", "raguard_knowledge_1024"]

        mock_meta_res = MagicMock()
        meta1 = VectorIndexMetadata(id=uuid.uuid4(), tenant_id="t-1", collection_name="raguard_knowledge_1536")
        mock_meta_res.scalars.return_value.all.return_value = [meta1]

        mock_session.execute.side_effect = [mock_col_res, mock_meta_res, mock_meta_res]

        ops = await service.delete_document_points(doc_id, "t-1")
        assert ops == 10  # 5 from each collection mock
        assert mock_provider.delete_points_by_filter.call_count == 2
        assert meta1.is_deleted is True


@pytest.mark.unit
class TestCeleryVectorWorker:
    """Test `sync_vectors_to_qdrant_task` Celery task execution and retry behavior."""

    @patch("backend.modules.vector.workers.tasks._async_sync_vectors_task")
    def test_sync_vectors_task_success(self, mock_async: MagicMock) -> None:
        from backend.modules.vector.workers.tasks import sync_vectors_to_qdrant_task

        mock_async.return_value = {
            "tenant_id": "tenant-1",
            "document_id": "doc-1",
            "document_version_id": "ver-1",
            "upserted_points": 42,
            "status": "COMPLETED",
        }

        res = sync_vectors_to_qdrant_task("doc-1", "ver-1", "tenant-1")
        assert res["upserted_points"] == 42
        assert res["status"] == "COMPLETED"

    @patch("backend.modules.vector.workers.tasks._async_sync_vectors_task")
    def test_sync_vectors_task_retry_on_recoverable_error(self, mock_async: MagicMock) -> None:
        from backend.modules.vector.workers.tasks import sync_vectors_to_qdrant_task

        mock_async.side_effect = QdrantConnectionError("Transient network timeout")

        sync_vectors_to_qdrant_task.push_request(retries=1)
        try:
            with patch.object(sync_vectors_to_qdrant_task, "retry", side_effect=RuntimeError("RetryTriggered")) as mock_retry:
                with pytest.raises(RuntimeError, match="RetryTriggered"):
                    sync_vectors_to_qdrant_task("doc-1", "ver-1", "tenant-1")
                mock_retry.assert_called_once()
                _, kwargs = mock_retry.call_args
                assert kwargs["countdown"] == 10  # 2**1 * 5 = 10s backoff
        finally:
            sync_vectors_to_qdrant_task.pop_request()
