"""Unit tests for IntegrityAuditor and StaleEmbeddingScanner (`ADR-M6-001`, `ADR-M6-002`)."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from backend.modules.knowledge_health.audits.integrity import IntegrityAuditor
from backend.modules.knowledge_health.audits.stale_scanner import StaleEmbeddingScanner
from backend.modules.vector.schemas.payload import CollectionSummaryDTO


@pytest.mark.asyncio
async def test_integrity_auditor_synced() -> None:
    """Verify that when DB chunks count == Qdrant points count, status is SYNCED."""
    session = AsyncMock()
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.delete = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    mock_pg_res = MagicMock()
    mock_pg_res.scalar_one_or_none.return_value = 50

    mock_cols_res = MagicMock()
    mock_cols_res.scalars.return_value.all.return_value = ["raguard_col_1536"]

    session.execute.side_effect = [mock_pg_res, mock_cols_res]

    provider = AsyncMock()
    provider.get_collection_info.return_value = CollectionSummaryDTO(
        collection_name="raguard_col_1536",
        points_count=50,
        indexed_vectors_count=50,
        vector_dimension=1536,
        status="green",
    )
    dispatcher = AsyncMock()

    auditor = IntegrityAuditor(session=session, provider=provider, dispatcher=dispatcher)
    audit = await auditor.verify_tenant_parity("tenant-A")

    assert audit.is_synced
    assert audit.pg_chunk_count == 50
    assert audit.qdrant_point_count == 50
    assert "SYNCED" in audit.parity_status
    dispatcher.publish.assert_not_called()


@pytest.mark.asyncio
async def test_integrity_auditor_mismatch_emits_drift_event() -> None:
    """Verify that when count parity fails, event is emitted and mismatch status returned."""
    session = AsyncMock()
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.delete = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    mock_pg_res = MagicMock()
    mock_pg_res.scalar_one_or_none.return_value = 60

    mock_cols_res = MagicMock()
    mock_cols_res.scalars.return_value.all.return_value = ["raguard_col_1536"]

    session.execute.side_effect = [mock_pg_res, mock_cols_res]

    provider = AsyncMock()
    provider.get_collection_info.return_value = CollectionSummaryDTO(
        collection_name="raguard_col_1536",
        points_count=40,
        indexed_vectors_count=40,
        vector_dimension=1536,
        status="green",
    )
    dispatcher = AsyncMock()

    auditor = IntegrityAuditor(session=session, provider=provider, dispatcher=dispatcher)
    audit = await auditor.verify_tenant_parity("tenant-A")

    assert not audit.is_synced
    assert audit.pg_chunk_count == 60
    assert audit.qdrant_point_count == 40
    assert "MISMATCH_DETECTED" in audit.parity_status
    dispatcher.publish.assert_called_once()


@pytest.mark.asyncio
async def test_stale_embedding_scanner_detection_and_reindex() -> None:
    """Verify identification of model configuration drift and creation of shadow re-index job."""
    session = AsyncMock()
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.delete = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    mock_emb = MagicMock()
    mock_emb.chunk_id = uuid4()
    mock_emb.provider = "openai"
    mock_emb.model_name = "text-embedding-ada-002"

    mock_execute_res = MagicMock()
    mock_execute_res.scalars.return_value.all.return_value = [mock_emb]
    session.execute.return_value = mock_execute_res

    repo = AsyncMock()
    repo.get_stale_records.return_value = []
    dispatcher = AsyncMock()

    scanner = StaleEmbeddingScanner(session=session, repository=repo, dispatcher=dispatcher)
    records = await scanner.detect_stale_embeddings(
        tenant_id="tenant-A",
        active_provider="openai",
        active_model="text-embedding-3-large",
    )

    assert len(records) == 1
    assert records[0].old_model_name == "text-embedding-ada-002"
    assert records[0].target_model_name == "text-embedding-3-large"
    dispatcher.publish.assert_called_once()

    job_id = await scanner.trigger_shadow_reindex(
        tenant_id="tenant-A",
        records=records,
        target_provider="openai",
        target_model="text-embedding-3-large",
    )
    assert job_id is not None
    repo.update_stale_record_status.assert_called_once_with(records[0].id, status="PROCESSING")
