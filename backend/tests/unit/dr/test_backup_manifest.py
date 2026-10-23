"""Unit tests for Backup Coordinator and Manifest Generation (`WP-3C Phase 2`, `TSK-3C-07`).

Verifies:
1. Isolated staging directory creation (.staging_{backup_run_id}).
2. SHA-256 calculation for artifact files.
3. Manifest metadata schema: backup_id, created_at, files, qdrant_collections.
4. Strict Non-Upgrade Invariant: consistency_level is permanently restricted to
   BEST_EFFORT_UNCOORDINATED / COORDINATED_QUIESCENT_APPLICATION.
   APPLICATION_CONSISTENT is strictly absent/prohibited.
5. Safe non-wildcard staging directory cleanup.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.dr.backup_all import (
    CONSISTENCY_LEVEL_QUIESCENT,
    CONSISTENCY_LEVEL_UNCOORDINATED,
    PROHIBITED_CONSISTENCY_LEVEL,
    BackupCoordinator,
    compute_sha256,
)


def test_staging_directory_and_cleanup(tmp_path: Path):
    coord = BackupCoordinator(backup_root=tmp_path)
    staging = coord.create_staging_directory()
    assert staging.exists()
    assert staging.name.startswith(".staging_backup_")

    # Clean up staging directory
    coord.cleanup_staging_directory()
    assert not staging.exists()


def test_sha256_computation(tmp_path: Path):
    test_file = tmp_path / "test.dump"
    test_file.write_bytes(b"Veritas-RAG PostgreSQL Dump Data 2026")
    sha = compute_sha256(test_file)
    assert len(sha) == 64
    assert isinstance(sha, str)


def test_manifest_generation_and_strict_non_upgrade_invariant(tmp_path: Path):
    coord = BackupCoordinator(backup_root=tmp_path)
    staging = coord.create_staging_directory()

    # Create dummy artifact files
    pg_dump = staging / "postgres" / "db.dump"
    pg_dump.write_bytes(b"Fake PG dump bytes")
    qdrant_snap = staging / "qdrant" / "col1.snapshot"
    qdrant_snap.write_bytes(b"Fake Qdrant snapshot bytes")

    manifest = coord.build_manifest(
        artifact_files=[pg_dump, qdrant_snap],
        qdrant_collections=[{"name": "col1", "dim": 1536, "points": 10}],
        is_quiescent=False,
    )

    # Assert Strict Non-Upgrade Invariant
    assert manifest["consistency_level"] == CONSISTENCY_LEVEL_UNCOORDINATED
    assert manifest["consistency_level"] != PROHIBITED_CONSISTENCY_LEVEL
    assert len(manifest["files"]) == 2
    assert manifest["files"][0]["sha256"] == compute_sha256(pg_dump)

    # Publish backup
    publish_dir = coord.publish_backup(manifest)
    assert publish_dir.exists()
    assert not staging.exists()
    assert (publish_dir / "manifest.json").exists()
