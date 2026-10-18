"""Unit tests for Pipeline Listeners and Lifecycle Version Correctness (Gates L1 and L2)."""

from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from backend.document.models.document import Document, DocumentVersion
from backend.document.models.status import DocumentStatus
from backend.tasks.listeners import (
    handle_chunking_completed,
    handle_document_processed,
    handle_embedding_completed,
    handle_vector_sync_completed,
)


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.commit = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_handle_document_processed_dispatches_correct_version_and_preserves_ready(mock_session):
    """Gate L1 & L2: When re-indexing V2 on a READY doc, dispatch V2 to chunking without demoting READY status."""
    doc_id = uuid.uuid4()
    v1_id = uuid.uuid4()
    v2_id = uuid.uuid4()
    tenant_id = "test-tenant"

    doc = Document(
        id=doc_id,
        tenant_id=tenant_id,
        status=DocumentStatus.READY,
        latest_version_id=v1_id,
        filename="contract.pdf",
    )

    mock_session.get.return_value = doc

    event = MagicMock()
    event.event_id = uuid.uuid4()
    event.data = {
        "document_id": str(doc_id),
        "document_version_id": str(v2_id),
        "version_id": str(v2_id),
    }
    event.payload = None

    with patch("backend.database.engine.get_session_factory") as mock_factory, \
         patch("backend.modules.chunking.workers.tasks.process_document_chunking_task.apply_async") as mock_chunk_task:
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_session
        mock_factory.return_value = MagicMock(return_value=mock_ctx)

        await handle_document_processed(event)

        # Verified: Dispatched version is V2, not latest_version_id (V1)
        mock_chunk_task.assert_called_once_with(
            args=[tenant_id, str(doc_id), str(v2_id)],
            queue="ingestion",
        )
        # Verified: Document remains READY for search queries
        assert doc.status == DocumentStatus.READY


@pytest.mark.asyncio
async def test_handle_document_processed_initial_version_transitions_to_chunking(mock_session):
    """Gate L2: Initial document upload (not yet READY) transitions to CHUNKING."""
    doc_id = uuid.uuid4()
    v1_id = uuid.uuid4()
    tenant_id = "test-tenant"

    doc = Document(
        id=doc_id,
        tenant_id=tenant_id,
        status=DocumentStatus.UPLOADED,
        latest_version_id=v1_id,
        filename="contract.pdf",
    )

    mock_session.get.return_value = doc

    event = MagicMock()
    event.event_id = uuid.uuid4()
    event.data = {
        "document_id": str(doc_id),
        "document_version_id": str(v1_id),
    }
    event.payload = None

    with patch("backend.database.engine.get_session_factory") as mock_factory, \
         patch("backend.modules.chunking.workers.tasks.process_document_chunking_task.apply_async") as mock_chunk_task:
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_session
        mock_factory.return_value = MagicMock(return_value=mock_ctx)

        await handle_document_processed(event)

        mock_chunk_task.assert_called_once_with(
            args=[tenant_id, str(doc_id), str(v1_id)],
            queue="ingestion",
        )
        assert doc.status == DocumentStatus.CHUNKING


@pytest.mark.asyncio
async def test_handle_chunking_completed_dispatches_correct_version_and_preserves_ready(mock_session):
    """Gate L1 & L2: When chunking completes for V2, initiate embedding for V2, keeping READY."""
    doc_id = uuid.uuid4()
    v1_id = uuid.uuid4()
    v2_id = uuid.uuid4()
    job_id = uuid.uuid4()
    tenant_id = "test-tenant"

    doc = Document(
        id=doc_id,
        tenant_id=tenant_id,
        status=DocumentStatus.READY,
        latest_version_id=v1_id,
        filename="contract.pdf",
    )

    mock_session.get.return_value = doc

    event = MagicMock()
    event.event_id = uuid.uuid4()
    event.document_id = doc_id
    event.document_version_id = v2_id
    event.data = {"chunk_count": 5}
    event.payload = None

    mock_emb_job = MagicMock()
    mock_emb_job.id = job_id

    with patch("backend.database.engine.get_session_factory") as mock_factory, \
         patch("backend.modules.embedding.services.embedding_service.EmbeddingService.initiate_embedding_job", new_callable=AsyncMock) as mock_initiate, \
         patch("backend.modules.embedding.workers.tasks.process_embedding_batch_task.apply_async") as mock_batch_task:
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_session
        mock_factory.return_value = MagicMock(return_value=mock_ctx)
        mock_initiate.return_value = mock_emb_job

        await handle_chunking_completed(event)

        # Verified: Embedding job initiated specifically with V2, not V1
        mock_initiate.assert_called_once()
        call_kwargs = mock_initiate.call_args.kwargs
        assert call_kwargs["document_version_id"] == v2_id
        assert call_kwargs["document_id"] == doc_id
        assert doc.status == DocumentStatus.READY
        mock_batch_task.assert_called_once()


@pytest.mark.asyncio
async def test_handle_embedding_completed_dispatches_correct_version_and_preserves_ready(mock_session):
    """Gate L1 & L2: When embedding completes for V2, dispatch vector sync for V2, keeping READY."""
    doc_id = uuid.uuid4()
    v1_id = uuid.uuid4()
    v2_id = uuid.uuid4()
    tenant_id = "test-tenant"

    doc = Document(
        id=doc_id,
        tenant_id=tenant_id,
        status=DocumentStatus.READY,
        latest_version_id=v1_id,
        filename="contract.pdf",
    )

    mock_session.get.return_value = doc

    payload_mock = MagicMock()
    payload_mock.document_id = str(doc_id)
    payload_mock.document_version_id = v2_id

    event = MagicMock()
    event.event_id = uuid.uuid4()
    event.payload = payload_mock
    event.data = {}

    with patch("backend.database.engine.get_session_factory") as mock_factory, \
         patch("backend.modules.vector.workers.tasks.sync_vectors_to_qdrant_task.apply_async") as mock_sync_task:
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_session
        mock_factory.return_value = MagicMock(return_value=mock_ctx)

        await handle_embedding_completed(event)

        # Verified: sync_vectors_to_qdrant_task receives V2, not doc.latest_version_id (V1)
        mock_sync_task.assert_called_once_with(
            args=[str(doc_id), str(v2_id), tenant_id],
            queue="indexing",
        )
        assert doc.status == DocumentStatus.READY


@pytest.mark.asyncio
async def test_handle_vector_sync_completed_promotes_monotonic_version(mock_session):
    """Gate L2: Vector sync for newer version V2 atomically promotes active version and sets latest_version_id."""
    doc_id = uuid.uuid4()
    v1_id = uuid.uuid4()
    v2_id = uuid.uuid4()
    tenant_id = "test-tenant"

    doc = Document(
        id=doc_id,
        tenant_id=tenant_id,
        status=DocumentStatus.READY,
        latest_version_id=v1_id,
        filename="contract.pdf",
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

    async def mock_get(model, entity_id):
        if model == DocumentVersion and entity_id == v2_id:
            return v2
        if model == DocumentVersion and entity_id == v1_id:
            return v1
        return None

    mock_session.get.side_effect = mock_get

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = doc
    mock_session.execute.return_value = mock_res

    event = MagicMock()
    event.event_id = uuid.uuid4()
    event.data = {"document_id": str(doc_id), "document_version_id": str(v2_id)}
    event.payload = None

    with patch("backend.database.engine.get_session_factory") as mock_factory, \
         patch("backend.document.repositories.document_repository.DocumentRepository.set_active_version", new_callable=AsyncMock) as mock_set_active:
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_session
        mock_factory.return_value = MagicMock(return_value=mock_ctx)

        await handle_vector_sync_completed(event)

        # Verified: Active version promoted to V2
        mock_set_active.assert_called_once_with(doc_id, v2_id, mock_session)
        assert doc.latest_version_id == v2_id
        assert doc.status == DocumentStatus.READY


@pytest.mark.asyncio
async def test_handle_vector_sync_completed_rejects_out_of_order_stale_version(mock_session):
    """Gate L2: Out-of-order vector sync for older version V1 does not regress already active V2."""
    doc_id = uuid.uuid4()
    v1_id = uuid.uuid4()
    v2_id = uuid.uuid4()
    tenant_id = "test-tenant"

    doc = Document(
        id=doc_id,
        tenant_id=tenant_id,
        status=DocumentStatus.READY,
        latest_version_id=v2_id,  # V2 is already active
        filename="contract.pdf",
    )
    v1 = DocumentVersion(
        id=v1_id,
        document_id=doc_id,
        version_number=1,
        is_active_vector=False,
    )
    v2 = DocumentVersion(
        id=v2_id,
        document_id=doc_id,
        version_number=2,
        is_active_vector=True,
    )

    async def mock_get(model, entity_id):
        if model == DocumentVersion and entity_id == v1_id:
            return v1
        if model == DocumentVersion and entity_id == v2_id:
            return v2
        return None

    mock_session.get.side_effect = mock_get

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = doc
    mock_session.execute.return_value = mock_res

    event = MagicMock()
    event.event_id = uuid.uuid4()
    event.data = {"document_id": str(doc_id), "document_version_id": str(v1_id)}
    event.payload = None

    with patch("backend.database.engine.get_session_factory") as mock_factory, \
         patch("backend.document.repositories.document_repository.DocumentRepository.set_active_version", new_callable=AsyncMock) as mock_set_active:
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_session
        mock_factory.return_value = MagicMock(return_value=mock_ctx)

        await handle_vector_sync_completed(event)

        # Verified: Active version NOT demoted to V1
        mock_set_active.assert_not_called()
        assert doc.latest_version_id == v2_id
        assert v1.is_active_vector is False
