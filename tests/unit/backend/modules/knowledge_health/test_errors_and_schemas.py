"""Unit tests for Knowledge Health error hierarchy and DTO schemas (`ADR-005`)."""

from datetime import UTC, datetime
from uuid import uuid4

from backend.modules.knowledge_health.schemas.errors import (
    InvalidScanTypeError,
    ModelRotationConflictError,
    ParityMismatchError,
    PurgeSynchronizationError,
    StaleEmbeddingScanError,
)
from backend.modules.knowledge_health.schemas.health_dto import (
    HealthScanJobDTO,
    HealthScanRequestDTO,
    ParityAuditDTO,
    PurgeSummaryDTO,
    ScanStatus,
    ScanType,
)


def test_error_taxonomy_codes_and_status() -> None:
    """Verify exact code mappings and HTTP status properties across all KHL errors."""
    err1 = InvalidScanTypeError(tenant_id="t1", scan_type="INVALID")
    assert err1.code == "KHL_001"
    assert err1.http_status == 400
    assert not err1.is_recoverable

    err2 = ParityMismatchError(tenant_id="t1", pg_count=10, qdrant_count=8)
    assert err2.code == "KHL_002"
    assert err2.http_status == 409
    assert err2.is_recoverable

    err3 = PurgeSynchronizationError(tenant_id="t1", document_id="doc-1", reason="Timeout")
    assert err3.code == "KHL_003"
    assert err3.http_status == 503
    assert err3.is_recoverable

    err4 = ModelRotationConflictError(tenant_id="t1", active_job_id="job-1")
    assert err4.code == "KHL_004"
    assert err4.http_status == 409
    assert not err4.is_recoverable

    err5 = StaleEmbeddingScanError(tenant_id="t1", reason="DB fail")
    assert err5.code == "KHL_005"
    assert err5.http_status == 500
    assert err5.is_recoverable


def test_health_dto_serialization() -> None:
    """Verify Pydantic DTO contracts and enum defaults."""
    req = HealthScanRequestDTO(scan_type=ScanType.ORPHAN_SWEEP)
    assert req.scan_type == ScanType.ORPHAN_SWEEP

    job = HealthScanJobDTO(
        id=uuid4(),
        tenant_id="t1",
        scan_type=ScanType.PARITY_AUDIT,
        status=ScanStatus.COMPLETED,
        orphans_found=5,
        orphans_purged=5,
        stale_chunks_found=0,
        parity_status="SYNCED (10 == 10)",
        duration_ms=12.5,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    assert job.status == ScanStatus.COMPLETED
    assert job.orphans_purged == 5

    parity = ParityAuditDTO(
        tenant_id="t1",
        pg_chunk_count=100,
        qdrant_point_count=100,
        is_synced=True,
        parity_status="SYNCED",
        checked_at=datetime.now(UTC),
    )
    assert parity.is_synced

    purge = PurgeSummaryDTO(
        document_id=uuid4(),
        tenant_id="t1",
        qdrant_points_deleted=15,
        pg_chunks_deleted=15,
        is_fully_purged=True,
        duration_ms=45.0,
    )
    assert purge.is_fully_purged
