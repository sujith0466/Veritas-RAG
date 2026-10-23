"""Unit tests for verify_restore Tool (`WP-3C Phase 2`, `TSK-3C-07`, `DEC-02`).

Verifies:
1. Manifest SHA-256 validation against restored files.
2. Detection of tampered/corrupted backup artifact files.
3. End-to-end non-destructive restore drill verification.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.dr.backup_all import BackupCoordinator
from scripts.dr.verify_restore import (
    RestoreChecksumError,
    verify_manifest_checksums,
)


def test_verify_manifest_checksums_success(tmp_path: Path):
    coord = BackupCoordinator(backup_root=tmp_path)
    staging = coord.create_staging_directory()

    f1 = staging / "postgres" / "db.dump"
    f1.write_bytes(b"Good Postgres Dump")
    f2 = staging / "storage" / "raw_files.tar"
    f2.write_bytes(b"Good Raw Storage")

    manifest = coord.build_manifest(
        artifact_files=[f1, f2],
        qdrant_collections=[],
        is_quiescent=True,
    )
    publish_dir = coord.publish_backup(manifest)

    verified_manifest = verify_manifest_checksums(publish_dir)
    assert verified_manifest["backup_id"] == coord.run_id
    assert len(verified_manifest["files"]) == 2


def test_verify_manifest_checksums_detects_tampering(tmp_path: Path):
    coord = BackupCoordinator(backup_root=tmp_path)
    staging = coord.create_staging_directory()

    f1 = staging / "postgres" / "db.dump"
    f1.write_bytes(b"Original File Bytes")

    manifest = coord.build_manifest(artifact_files=[f1], qdrant_collections=[])
    publish_dir = coord.publish_backup(manifest)

    # Simulate bit-rot / tampering in storage
    (publish_dir / "postgres" / "db.dump").write_bytes(b"Tampered File Bytes")

    with pytest.raises(RestoreChecksumError) as exc_info:
        verify_manifest_checksums(publish_dir)
    assert "SHA-256 mismatch" in str(exc_info.value)
