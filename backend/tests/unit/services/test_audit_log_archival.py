"""Unit and Tamper-Detection tests for Audit Log WORM Archival Engine (F15.7).

Validates:
1. Deterministic canonical serialization and SHA-256 chained hashing.
2. Verification success on unmodified pristine archives.
3. Tamper detection on modified record fields (payload tampering).
4. Tamper detection on deleted/missing records.
5. Tamper detection on injected unauthorized records.
6. Tamper detection on reordered records (chain break).
7. Tamper detection on forged manifest metadata.
8. Strict tenant boundary isolation during archive creation.
"""

import datetime
import uuid

import pytest

from backend.models.entities.audit_log import AuditLog
from backend.services.audit.archival_service import (
    AuditLogArchivalService,
)


def create_sample_logs(tenant_id: uuid.UUID, count: int = 5) -> list[AuditLog]:
    """Helper to create dummy AuditLog entities."""
    base_time = datetime.datetime(2026, 8, 1, 10, 0, 0, tzinfo=datetime.timezone.utc)
    logs = []
    for i in range(count):
        log = AuditLog(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            action=f"security.event.{i}",
            user_id=uuid.uuid4(),
            resource_type="workspace",
            resource_id=f"res_{i}",
            details={"ip": f"192.168.1.{i}", "attempt": i},
            status="success",
            created_at=base_time + datetime.timedelta(minutes=i),
        )
        logs.append(log)
    return logs


def test_archive_creation_and_pristine_verification():
    """Verify archive packaging and successful cryptographic verification of pristine archives."""
    tenant_id = uuid.uuid4()
    logs = create_sample_logs(tenant_id, count=5)
    start_time = datetime.datetime(2026, 8, 1, 0, 0, tzinfo=datetime.timezone.utc)
    end_time = datetime.datetime(2026, 8, 2, 0, 0, tzinfo=datetime.timezone.utc)

    records_data, manifest = AuditLogArchivalService.build_archive_package(
        records=logs,
        tenant_id=tenant_id,
        period_start=start_time,
        period_end=end_time,
    )

    assert len(records_data) == 5
    assert manifest.record_count == 5
    assert manifest.tenant_id == str(tenant_id)
    assert manifest.algorithm == "SHA256-CHAIN-v1"
    assert len(manifest.root_hash) == 64

    # Verify pristine archive
    result = AuditLogArchivalService.verify_archive_integrity(records_data, manifest)
    assert result.is_valid is True
    assert result.record_count == 5
    assert result.error_message is None


def test_tamper_detection_modified_record_payload():
    """Verify that tampering with any field in a record produces a deterministic verification failure."""
    tenant_id = uuid.uuid4()
    logs = create_sample_logs(tenant_id, count=4)
    start_time = datetime.datetime(2026, 8, 1, 0, 0, tzinfo=datetime.timezone.utc)
    end_time = datetime.datetime(2026, 8, 2, 0, 0, tzinfo=datetime.timezone.utc)

    records_data, manifest = AuditLogArchivalService.build_archive_package(
        records=logs,
        tenant_id=tenant_id,
        period_start=start_time,
        period_end=end_time,
    )

    # Maliciously alter action in record index 2
    records_data[2]["action"] = "malicious.tampered.action"

    result = AuditLogArchivalService.verify_archive_integrity(records_data, manifest)
    assert result.is_valid is False
    assert result.mismatched_index == 2
    assert "Record tamper detected at index 2" in result.error_message


def test_tamper_detection_deleted_record():
    """Verify that deleting a record from the archive triggers a count and chain mismatch."""
    tenant_id = uuid.uuid4()
    logs = create_sample_logs(tenant_id, count=4)
    start_time = datetime.datetime(2026, 8, 1, 0, 0, tzinfo=datetime.timezone.utc)
    end_time = datetime.datetime(2026, 8, 2, 0, 0, tzinfo=datetime.timezone.utc)

    records_data, manifest = AuditLogArchivalService.build_archive_package(
        records=logs,
        tenant_id=tenant_id,
        period_start=start_time,
        period_end=end_time,
    )

    # Maliciously delete one record
    records_data.pop(1)

    result = AuditLogArchivalService.verify_archive_integrity(records_data, manifest)
    assert result.is_valid is False
    assert "Record count mismatch" in result.error_message


def test_tamper_detection_injected_record():
    """Verify that injecting an unauthorized record triggers verification failure."""
    tenant_id = uuid.uuid4()
    logs = create_sample_logs(tenant_id, count=3)
    start_time = datetime.datetime(2026, 8, 1, 0, 0, tzinfo=datetime.timezone.utc)
    end_time = datetime.datetime(2026, 8, 2, 0, 0, tzinfo=datetime.timezone.utc)

    records_data, manifest = AuditLogArchivalService.build_archive_package(
        records=logs,
        tenant_id=tenant_id,
        period_start=start_time,
        period_end=end_time,
    )

    # Injected record
    fake_record = {
        "id": str(uuid.uuid4()),
        "created_at": "2026-08-01T12:00:00+00:00",
        "tenant_id": str(tenant_id),
        "action": "fake.injected.action",
        "user_id": str(uuid.uuid4()),
        "resource_type": "auth",
        "resource_id": "none",
        "details_json": "{}",
        "status": "success",
        "record_hash": "deadbeef" * 8,
    }
    records_data.append(fake_record)

    result = AuditLogArchivalService.verify_archive_integrity(records_data, manifest)
    assert result.is_valid is False


def test_tamper_detection_reordered_records():
    """Verify that reordering records in the archive breaks cryptographic chain integrity."""
    tenant_id = uuid.uuid4()
    logs = create_sample_logs(tenant_id, count=4)
    start_time = datetime.datetime(2026, 8, 1, 0, 0, tzinfo=datetime.timezone.utc)
    end_time = datetime.datetime(2026, 8, 2, 0, 0, tzinfo=datetime.timezone.utc)

    records_data, manifest = AuditLogArchivalService.build_archive_package(
        records=logs,
        tenant_id=tenant_id,
        period_start=start_time,
        period_end=end_time,
    )

    # Swap record 0 and record 1
    records_data[0], records_data[1] = records_data[1], records_data[0]

    result = AuditLogArchivalService.verify_archive_integrity(records_data, manifest)
    assert result.is_valid is False
    assert "Root integrity mismatch" in result.error_message


def test_tamper_detection_forged_manifest_root():
    """Verify that forging the manifest root hash fails verification."""
    tenant_id = uuid.uuid4()
    logs = create_sample_logs(tenant_id, count=3)
    start_time = datetime.datetime(2026, 8, 1, 0, 0, tzinfo=datetime.timezone.utc)
    end_time = datetime.datetime(2026, 8, 2, 0, 0, tzinfo=datetime.timezone.utc)

    records_data, manifest = AuditLogArchivalService.build_archive_package(
        records=logs,
        tenant_id=tenant_id,
        period_start=start_time,
        period_end=end_time,
    )

    # Manifest with forged root hash
    forged_manifest = manifest.to_dict()
    forged_manifest["root_hash"] = "ffffffff" * 8

    result = AuditLogArchivalService.verify_archive_integrity(records_data, forged_manifest)
    assert result.is_valid is False
    assert "Root integrity mismatch" in result.error_message


def test_tenant_boundary_isolation():
    """Verify that build_archive_package rejects records belonging to a different tenant."""
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()

    log_a = create_sample_logs(tenant_a, count=1)[0]
    log_b = create_sample_logs(tenant_b, count=1)[0]

    start_time = datetime.datetime(2026, 8, 1, 0, 0, tzinfo=datetime.timezone.utc)
    end_time = datetime.datetime(2026, 8, 2, 0, 0, tzinfo=datetime.timezone.utc)

    with pytest.raises(ValueError, match="Cross-tenant pollution detected"):
        AuditLogArchivalService.build_archive_package(
            records=[log_a, log_b],
            tenant_id=tenant_a,
            period_start=start_time,
            period_end=end_time,
        )


def test_empty_archive_package():
    """Verify that an empty record set produces a valid archive package with genesis hash."""
    tenant_id = uuid.uuid4()
    start_time = datetime.datetime(2026, 8, 1, 0, 0, tzinfo=datetime.timezone.utc)
    end_time = datetime.datetime(2026, 8, 2, 0, 0, tzinfo=datetime.timezone.utc)

    records_data, manifest = AuditLogArchivalService.build_archive_package(
        records=[],
        tenant_id=tenant_id,
        period_start=start_time,
        period_end=end_time,
    )

    assert len(records_data) == 0
    assert manifest.record_count == 0
    assert manifest.root_hash == AuditLogArchivalService.GENESIS_HASH

    result = AuditLogArchivalService.verify_archive_integrity(records_data, manifest)
    assert result.is_valid is True
    assert result.record_count == 0
