"""Unit tests for PurgeOrchestrator and OrphanCleanupEngine (`ADR-M6-001`)."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from backend.modules.knowledge_health.cleanups.orphans import OrphanCleanupEngine
from backend.modules.knowledge_health.cleanups.purge import PurgeOrchestrator
from backend.modules.knowledge_health.schemas.errors import PurgeSynchronizationError


@pytest.mark.asyncio
async def test_two_phase_purge_success() -> None:
    """Verify clean execution of two-phase document and vector purge."""
    session = AsyncMock()
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.delete = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    # Mock document select
    mock_doc = MagicMock()
    mock_doc.id = uuid4()
    mock_doc.status = "PENDING"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_doc
    mock_result.scalars.return_value.all.return_value = []
    session.execute.return_value = mock_result

    vec_service = AsyncMock()
    vec_service.delete_document_points.return_value = 10
    dispatcher = AsyncMock()

    orchestrator = PurgeOrchestrator(session=session, vector_service=vec_service, dispatcher=dispatcher)
    summary = await orchestrator.execute_two_phase_purge(document_id=mock_doc.id, tenant_id="tenant-A")

    assert summary.qdrant_points_deleted == 10
    assert summary.is_fully_purged
    assert mock_doc.status == "DELETED"
    assert mock_doc.is_deleted
    dispatcher.publish.assert_called_once()


@pytest.mark.asyncio
async def test_two_phase_purge_vector_failure_raises_khl_003() -> None:
    """Verify that when finalize_hard_purge raises an unexpected error, PurgeSynchronizationError is thrown while DB remains marked DELETED."""
    session = AsyncMock()
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.delete = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    mock_doc = MagicMock()
    mock_doc.id = uuid4()

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_doc
    mock_result.scalars.return_value.all.return_value = []
    session.execute.return_value = mock_result

    vec_service = AsyncMock()
    # If session execute inside finalize_hard_purge raises Exception, test rollback/recovery wrapper
    session.execute.side_effect = [
        mock_result,  # Document check
        mock_result,  # DocumentVersion check
        mock_result,  # DocumentChunk check
        Exception("DB Connection Drop"),  # delete during finalize_hard_purge
    ]

    orchestrator = PurgeOrchestrator(session=session, vector_service=vec_service)

    with pytest.raises(PurgeSynchronizationError) as exc_info:
        await orchestrator.execute_two_phase_purge(document_id=mock_doc.id, tenant_id="tenant-A")

    assert exc_info.value.code == "KHL_003"
    assert mock_doc.status == "DELETED"


@pytest.mark.asyncio
async def test_orphan_cleanup_engine_sweep() -> None:
    """Verify identification and sweeping of orphaned chunks lacking active parent documents."""
    session = AsyncMock()
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.delete = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    # Mock active documents query returning active doc ID
    active_doc_id = uuid4()
    orphan_doc_id = uuid4()

    mock_active_res = MagicMock()
    mock_active_res.scalars.return_value.all.return_value = [active_doc_id]

    mock_chunk1 = MagicMock()
    mock_chunk1.id = uuid4()
    mock_chunk1.document_id = active_doc_id
    mock_chunk1.is_deleted = False

    mock_chunk2 = MagicMock()
    mock_chunk2.id = uuid4()
    mock_chunk2.document_id = orphan_doc_id  # Orphaned parent doc!
    mock_chunk2.is_deleted = False

    mock_chunk_res = MagicMock()
    mock_chunk_res.scalars.return_value.all.return_value = [mock_chunk1, mock_chunk2]

    session.execute.side_effect = [
        mock_active_res,
        mock_chunk_res,
        MagicMock(),  # delete ChunkEmbedding
        MagicMock(),  # delete VectorIndexMetadata
        MagicMock(),  # delete DocumentChunk
    ]

    vec_service = AsyncMock()
    vec_service.delete_document_points.return_value = 2

    engine = OrphanCleanupEngine(session=session, vector_service=vec_service)
    count = await engine.sweep_orphaned_chunks(tenant_id="tenant-A")

    assert count == 1
    vec_service.delete_document_points.assert_called_once_with(document_id=orphan_doc_id, tenant_id="tenant-A")
