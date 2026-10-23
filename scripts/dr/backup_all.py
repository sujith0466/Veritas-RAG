"""Multi-Store Backup Coordinator (`WP-3C Phase 2`, `TSK-3C-07`, `DEC-01`).

Orchestrates multi-store backups across PostgreSQL, dynamic Qdrant collections,
and storage artifacts with SHA-256 checksum manifests and isolated staging directories.
Enforces the Strict Non-Upgrade Invariant: consistency_level is permanently restricted
to BEST_EFFORT_UNCOORDINATED; APPLICATION_CONSISTENT is strictly prohibited.
"""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from typing import Any
import uuid

import structlog

logger = structlog.get_logger(__name__)

CONSISTENCY_LEVEL_UNCOORDINATED = "BEST_EFFORT_UNCOORDINATED"
CONSISTENCY_LEVEL_QUIESCENT = "COORDINATED_QUIESCENT_APPLICATION"
PROHIBITED_CONSISTENCY_LEVEL = "APPLICATION_CONSISTENT"


def compute_sha256(file_path: Path) -> str:
    """Compute SHA-256 checksum of a file."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


class BackupCoordinator:
    """Coordinates multi-store backup capture, staging, checksum generation, and publication."""

    def __init__(
        self,
        backup_root: Path | str = "/app/backups",
        quiescence_enabled: bool = False,
    ) -> None:
        self.backup_root = Path(backup_root)
        self.quiescence_enabled = quiescence_enabled
        self.run_id = f"backup_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        self.staging_dir = self.backup_root / f".staging_{self.run_id}"
        self.publish_dir = self.backup_root / self.run_id

    def create_staging_directory(self) -> Path:
        """Create isolated staging directory for this backup run."""
        self.staging_dir.mkdir(parents=True, exist_ok=True)
        (self.staging_dir / "postgres").mkdir(exist_ok=True)
        (self.staging_dir / "qdrant").mkdir(exist_ok=True)
        (self.staging_dir / "storage").mkdir(exist_ok=True)
        return self.staging_dir

    def cleanup_staging_directory(self) -> None:
        """Safely delete interim staging directory using exact path (no wildcards)."""
        if self.staging_dir.exists():
            shutil.rmtree(self.staging_dir, ignore_errors=True)
            logger.info("Purged staging directory", staging_dir=str(self.staging_dir))

    def build_manifest(
        self,
        artifact_files: list[Path],
        qdrant_collections: list[dict[str, Any]],
        is_quiescent: bool = False,
        status: str = "PUBLISHED",
    ) -> dict[str, Any]:
        """Build backup manifest with SHA-256 checksums and explicit consistency classification."""
        manifest_files: list[dict[str, Any]] = []
        for p in artifact_files:
            if p.is_file():
                rel_path = str(p.relative_to(self.staging_dir))
                size_bytes = p.stat().st_size
                checksum = compute_sha256(p)
                manifest_files.append({
                    "path": rel_path,
                    "size_bytes": size_bytes,
                    "sha256": checksum,
                })

        # Strict Non-Upgrade Invariant: APPLICATION_CONSISTENT is strictly prohibited
        consistency = (
            CONSISTENCY_LEVEL_QUIESCENT
            if is_quiescent
            else CONSISTENCY_LEVEL_UNCOORDINATED
        )

        manifest = {
            "backup_id": self.run_id,
            "created_at": datetime.now(UTC).isoformat(),
            "consistency_level": consistency,
            "certification_status": status,
            "storage_fencing_disclaimer": (
                "Heterogeneous multi-store atomicity across PostgreSQL, MinIO, and Qdrant "
                "is disclaimed without 2PC. Quiescence enforces application-level admission barriers."
            ),
            "files": manifest_files,
            "qdrant_collections": qdrant_collections,
        }
        return manifest

    def publish_backup(self, manifest: dict[str, Any]) -> Path:
        """Write manifest and atomically rename staging directory to published backup directory."""
        manifest_path = self.staging_dir / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        self.staging_dir.rename(self.publish_dir)
        logger.info(
            "Backup published successfully",
            backup_id=self.run_id,
            publish_dir=str(self.publish_dir),
            consistency_level=manifest["consistency_level"],
        )
        return self.publish_dir
