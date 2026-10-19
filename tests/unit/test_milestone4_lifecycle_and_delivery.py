"""Unit tests for Milestone 4: Document Lifecycle Integrity & Zero-Downtime Serving (AUD-005, AUD-006, AUD-007)."""

import asyncio
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import pytest

from backend.core.events.base import BaseEvent
from backend.core.events.dispatcher import EventDispatcher
from backend.core.events.types import EventType
from backend.document.events import EVENT_DOCUMENT_PROCESSED
from backend.document.models.document import Document, DocumentVersion
from backend.document.models.status import DocumentStatus
from backend.modules.chunking.models.chunk import DocumentChunk  # Required for mapper initialization
from backend.modules.embedding.models.chunk_embedding import ChunkEmbedding  # Required for mapper initialization
from backend.document.services.failure_service import PipelineFailureSynchronizer
from backend.tasks.listeners import (
    handle_chunking_completed,
    handle_document_processed,
    handle_embedding_completed,
    handle_vector_sync_completed,
)


@dataclass(frozen=True)
class DummyEvent(BaseEvent):
    tenant_id: str = "tenant-test-123"
    document_id: str = "doc-test-456"
    data: dict = None


# ==============================================================================
# AUD-005 Tests: Awaited Delivery in Worker Contexts & Inspection Loop
# ==============================================================================

def test_aud005_await_delivery_with_failing_handler_and_redis():
    """Verify publish(await_delivery=True) gathers delivery coroutines, completes without raising, and logs errors."""
    def run_worker_task():
        dispatcher = EventDispatcher()
        event = DummyEvent(
            event_type=EventType.DOCUMENT_UPLOADED,
            tenant_id=str(uuid.uuid4()),
            data={"status": "processing"}
        )

        failing_handler = AsyncMock(side_effect=RuntimeError("Handler crashed deliberately"))
        failing_handler.__qualname__ = "failing_dummy_handler"
        dispatcher.subscribe(EventType.DOCUMENT_UPLOADED, failing_handler)

        mock_redis_client = AsyncMock()
        mock_redis_client.publish.side_effect = ConnectionError("Redis broker connection dropped")
        mock_redis_client.aclose = AsyncMock()

        logged_errors = []

        def fake_logger_error(msg, **kwargs):
            logged_errors.append((msg, kwargs))

        with patch("redis.asyncio.from_url", return_value=mock_redis_client), \
             patch("backend.tasks.webhooks.deliver_webhook_event_task.delay"), \
             patch("backend.core.events.dispatcher.logger.error", side_effect=fake_logger_error):
            # Must run cleanly without raising in worker asyncio context
            asyncio.run(dispatcher.publish(event, await_delivery=True))

        # (a) Verify asyncio.gather completed and failing handler was executed
        assert failing_handler.called

        # (b) Verify that logger.error was called for both failing handler and failing redis delivery
        error_messages = [msg for msg, _ in logged_errors]
        assert "Event handler raised an exception" in error_messages
        assert "Event delivery task raised an exception" in error_messages

        # (c) Verify error details captured
        delivery_err = next(kw for msg, kw in logged_errors if msg == "Event delivery task raised an exception")
        assert delivery_err.get("handler") == "redis_pubsub"
        assert "Redis broker connection dropped" in delivery_err.get("error")

        handler_err = next(kw for msg, kw in logged_errors if msg == "Event handler raised an exception")
        assert handler_err.get("handler") == "failing_dummy_handler"
        assert "Handler crashed deliberately" in handler_err.get("error")

    run_worker_task()


# ==============================================================================
# AUD-006 Tests: Broker Failure & Multi-Version Active Serving Preservation
# ==============================================================================

@pytest.mark.asyncio
async def test_aud006_chunking_dispatch_failure_preserves_active_v1():
    """When broker is down during V2 chunking dispatch, V1 remains serving (READY) and V2 is marked inactive."""
    doc_id = uuid.uuid4()
    v1_id = uuid.uuid4()
    v2_id = uuid.uuid4()

    mock_doc = Document(
        id=doc_id,
        tenant_id="tenant-multi-ver",
        status=DocumentStatus.READY,
        latest_version_id=v1_id,
        filename="report.pdf",
    )
    v1 = DocumentVersion(
        id=v1_id,
        document_id=doc_id,
        version_number=1,
        is_active_vector=True,
        is_deleted=False,
    )
    v2 = DocumentVersion(
        id=v2_id,
        document_id=doc_id,
        version_number=2,
        is_active_vector=True,
        is_deleted=False,
    )

    mock_session = AsyncMock()

    async def mock_get(model, entity_id):
        if model == Document and entity_id == doc_id:
            return mock_doc
        return None

    mock_session.get.side_effect = mock_get
    mock_exec_res = MagicMock()
    mock_exec_res.scalars.return_value.all.return_value = [v1, v2]
    mock_exec_res.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_exec_res

    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_session

    event = DummyEvent(
        event_type=EVENT_DOCUMENT_PROCESSED,
        tenant_id="tenant-multi-ver",
        document_id=str(doc_id),
        data={"document_id": str(doc_id), "document_version_id": str(v2_id)},
    )

    with patch("backend.database.engine.get_session_factory", return_value=mock_session_factory), \
         patch("backend.modules.chunking.workers.tasks.process_document_chunking_task.apply_async", side_effect=Exception("RabbitMQ connection refused")):
        await handle_document_processed(event)

    # Document must PRESERVE READY status for online RAG serving
    assert mock_doc.status == DocumentStatus.READY
    # In-flight V2 must be deactivated
    assert v2.is_active_vector is False
    assert v1.is_active_vector is True
    assert mock_session.commit.called


@pytest.mark.asyncio
async def test_aud006_chunking_dispatch_failure_initial_upload_marks_failed():
    """Initial upload (no previous active version) transitions to FAILED on broker failure."""
    doc_id = uuid.uuid4()
    v1_id = uuid.uuid4()

    mock_doc = Document(
        id=doc_id,
        tenant_id="tenant-initial",
        status=DocumentStatus.PROCESSED,
        latest_version_id=v1_id,
        filename="initial.pdf",
    )
    v1 = DocumentVersion(
        id=v1_id,
        document_id=doc_id,
        version_number=1,
        is_active_vector=True,
        is_deleted=False,
    )

    mock_session = AsyncMock()

    async def mock_get(model, entity_id):
        if model == Document and entity_id == doc_id:
            return mock_doc
        return None

    mock_session.get.side_effect = mock_get
    mock_exec_res = MagicMock()
    mock_exec_res.scalars.return_value.all.return_value = [v1]
    mock_exec_res.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_exec_res

    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_session

    event = DummyEvent(
        event_type=EVENT_DOCUMENT_PROCESSED,
        tenant_id="tenant-initial",
        document_id=str(doc_id),
        data={"document_id": str(doc_id), "document_version_id": str(v1_id)},
    )

    with patch("backend.database.engine.get_session_factory", return_value=mock_session_factory), \
         patch("backend.modules.chunking.workers.tasks.process_document_chunking_task.apply_async", side_effect=Exception("Broker unreachable")):
        await handle_document_processed(event)

    # With no other active version, document transitions to FAILED
    assert mock_doc.status == DocumentStatus.FAILED
    assert v1.is_active_vector is False
    assert mock_session.commit.called


# ==============================================================================
# AUD-007 Tests: Post-Promotion Vector Cleanup & Recovery
# ==============================================================================

@pytest.mark.asyncio
async def test_aud007_sync_document_vectors_does_not_purge_old_vectors():
    """sync_document_vectors must not call cleanup_old_versions_vectors prematurely."""
    from backend.modules.vector.services.vector_service import VectorStorageService

    mock_session = AsyncMock()
    mock_repo = MagicMock()
    mock_provider = AsyncMock()

    service = VectorStorageService(session=mock_session, provider=mock_provider)
    service.repo = mock_repo
    service.cleanup_old_versions_vectors = AsyncMock()

    doc_id = uuid.uuid4()
    ver_id = uuid.uuid4()
    tenant_id = "tenant-zero-downtime"

    mock_rec = MagicMock()
    mock_rec.id = uuid.uuid4()
    mock_repo.get_or_create_metadata = AsyncMock(return_value=mock_rec)
    mock_repo.update_sync_status = AsyncMock()

    # Mock chunk embeddings
    mock_chunk = MagicMock()
    mock_chunk.id = uuid.uuid4()
    mock_chunk.chunk_index = 0
    mock_chunk.content = "sample chunk"
    mock_chunk.metadata_json = {}
    mock_chunk.embedding = MagicMock()
    mock_chunk.embedding.vector = [0.1] * 384

    mock_exec_res = MagicMock()
    mock_exec_res.scalars.return_value.all.return_value = [mock_chunk]
    mock_session.execute.return_value = mock_exec_res

    mock_provider.upsert_points = AsyncMock()
    mock_provider.get_collection_dimension = AsyncMock(return_value=384)

    with patch("backend.modules.vector.services.vector_service.acquire_lock") as mock_lock:
        mock_lock.return_value.__aenter__.return_value = "lock-token"
        await service.sync_document_vectors(
            tenant_id=tenant_id,
            document_id=doc_id,
            document_version_id=ver_id,
        )

    # CRITICAL: Verify cleanup was NOT invoked during vector sync!
    assert not service.cleanup_old_versions_vectors.called
    assert mock_provider.upsert_points.called


@pytest.mark.asyncio
async def test_aud007_post_promotion_cleanup_in_vector_sync_completed():
    """handle_vector_sync_completed promotes active version first, then executes cleanup."""
    doc_id = uuid.uuid4()
    v1_id = uuid.uuid4()
    v2_id = uuid.uuid4()

    mock_doc = Document(
        id=doc_id,
        tenant_id="tenant-cleanup",
        status=DocumentStatus.VECTOR_SYNC,
        latest_version_id=v1_id,
        filename="doc.pdf",
    )
    v1 = DocumentVersion(
        id=v1_id,
        document_id=doc_id,
        version_number=1,
        is_active_vector=True,
    )
    v2 = DocumentVersion(
        id=v2_id,
        document_id=doc_id,
        version_number=2,
        is_active_vector=False,
    )

    mock_session = AsyncMock()

    async def mock_get(model, entity_id):
        if model == DocumentVersion and entity_id == v2_id:
            return v2
        if model == DocumentVersion and entity_id == v1_id:
            return v1
        return None

    mock_session.get.side_effect = mock_get
    mock_exec_res = MagicMock()
    mock_exec_res.scalar_one_or_none.return_value = mock_doc
    mock_session.execute.return_value = mock_exec_res

    mock_session_factory = MagicMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_session

    cleanup_mock = AsyncMock(return_value=5)

    event = DummyEvent(
        event_type=EventType.VECTORS_INDEXED,
        tenant_id="tenant-cleanup",
        document_id=str(doc_id),
        data={"document_id": str(doc_id), "document_version_id": str(v2_id)},
    )

    with patch("backend.database.engine.get_session_factory", return_value=mock_session_factory), \
         patch("backend.document.repositories.document_repository.DocumentRepository.set_active_version", new_callable=AsyncMock) as mock_set_active, \
         patch("backend.modules.vector.services.vector_service.VectorStorageService.cleanup_old_versions_vectors", cleanup_mock):
        await handle_vector_sync_completed(event)

    # 1. Active version promoted
    assert mock_doc.status == DocumentStatus.READY
    assert mock_doc.latest_version_id == v2_id
    mock_set_active.assert_called_once_with(doc_id, v2_id, mock_session)

    # 2. Cleanup called strictly post-promotion
    cleanup_mock.assert_called_once_with(
        document_id=doc_id,
        current_version_id=v2_id,
        tenant_id="tenant-cleanup",
    )
