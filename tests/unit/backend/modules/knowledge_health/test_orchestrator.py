"""Unit tests for KnowledgeHealthOrchestrator domain service (`ADR-005`)."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from backend.modules.knowledge_health.models.health_scan import HealthScanJob
from backend.modules.knowledge_health.schemas.errors import InvalidScanTypeError
from backend.modules.knowledge_health.schemas.health_dto import ScanStatus, ScanType
from backend.modules.knowledge_health.services.health_service import KnowledgeHealthOrchestrator


@pytest.mark.asyncio
async def test_orchestrator_run_all_scans() -> None:
    """Verify execution of ScanType.ALL invoking orphan sweep, parity audit, and drift detection."""
    session = AsyncMock()
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.delete = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    vec_service = AsyncMock()
    dispatcher = AsyncMock()

    orchestrator = KnowledgeHealthOrchestrator(session=session, vector_service=vec_service, dispatcher=dispatcher)

    # Mock internal engines
    orchestrator.orphan_engine = AsyncMock()
    orchestrator.orphan_engine.sweep_orphaned_chunks.return_value = 3

    mock_audit = MagicMock()
    mock_audit.parity_status = "SYNCED (25 == 25)"
    orchestrator.auditor = AsyncMock()
    orchestrator.auditor.verify_tenant_parity.return_value = mock_audit

    orchestrator.stale_scanner = AsyncMock()
    orchestrator.stale_scanner.detect_stale_embeddings.return_value = [MagicMock(), MagicMock()]

    # Mock repo logging and updating
    job_id = uuid4()
    orchestrator.repo = AsyncMock()
    orchestrator.repo.log_scan_job.return_value = job_id

    mock_job = HealthScanJob(
        id=job_id,
        tenant_id="tenant-A",
        scan_type="ALL",
        status="COMPLETED",
        orphans_found=3,
        orphans_purged=3,
        stale_chunks_found=2,
        parity_status="SYNCED (25 == 25)",
        duration_ms=10.0,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    orchestrator.repo.update_scan_progress.return_value = mock_job

    dto = await orchestrator.run_health_scan(tenant_id="tenant-A", scan_type=ScanType.ALL)

    assert dto.id == job_id
    assert dto.status == ScanStatus.COMPLETED
    assert dto.orphans_purged == 3
    assert dto.stale_chunks_found == 2
    assert "SYNCED" in dto.parity_status
    assert dispatcher.publish.call_count == 2  # Started and Completed events


@pytest.mark.asyncio
async def test_orchestrator_invalid_scan_type_raises_error() -> None:
    """Verify that an unsupported scan string raises InvalidScanTypeError before execution."""
    session = AsyncMock()
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.delete = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    orchestrator = KnowledgeHealthOrchestrator(session=session)

    with pytest.raises(InvalidScanTypeError) as exc:
        await orchestrator.run_health_scan(tenant_id="tenant-A", scan_type="BOGUS_SCAN")  # type: ignore[arg-type]

    assert exc.value.code == "KHL_001"
