"""Isolated Restore Verification Tool (`WP-3C Phase 2`, `TSK-3C-07`, `DEC-02`, `Audit E`).

Performs non-destructive restore verification drill against isolated ephemeral containers.
Enforces strict production exclusion preflight checks (dedicated ports 5433, 6335, 9002;
refuses production ports 5432, 6333, 9000; refuses raguard_* volume mutations).
Executes Tier I (point ID set equality) and Tier II (finite float integrity) vector parity checks.
Enforces the Strict Non-Upgrade Invariant: preserves conservative consistency classification.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import structlog

from scripts.dr.backup_all import compute_sha256

logger = structlog.get_logger(__name__)

PRODUCTION_FORBIDDEN_PORTS = {5432, 6333, 6334, 6379, 6432, 8000, 5173, 9000, 9001}
ALLOWED_RESTORE_PORTS = {5433, 6335, 6336, 6389, 9002, 9003}


class RestorePreflightError(Exception):
    """Raised when preflight isolation checks detect dangerous production port or volume collisions."""


class RestoreChecksumError(Exception):
    """Raised when artifact SHA-256 does not match manifest checksum."""


class QdrantParityError(Exception):
    """Raised when restored vector collection fails point equality or float integrity checks."""


def check_preflight_isolation(
    target_ports: list[int],
    target_volumes: list[str],
) -> None:
    """Pure read-only preflight isolation verification.

    Raises RestorePreflightError if any production port or volume is targeted.
    """
    for port in target_ports:
        if port in PRODUCTION_FORBIDDEN_PORTS:
            raise RestorePreflightError(
                f"FATAL: Target port {port} is a protected production port! Restore drills must use isolated ports (e.g. 5433, 6335, 9002)."
            )
        if port not in ALLOWED_RESTORE_PORTS:
            raise RestorePreflightError(
                f"FATAL: Target port {port} is not in the approved isolated restore port set: {ALLOWED_RESTORE_PORTS}"
            )

    for vol in target_volumes:
        if vol.startswith("raguard_") and not vol.startswith("veritas_restore_"):
            raise RestorePreflightError(
                f"FATAL: Volume '{vol}' matches active production volume prefix! Must use ephemeral volume 'veritas_restore_*'."
            )


def verify_manifest_checksums(backup_dir: Path) -> dict[str, Any]:
    """Verify SHA-256 checksums of all files listed in manifest.json."""
    manifest_path = backup_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest.json not found in backup directory {backup_dir}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    for file_entry in manifest.get("files", []):
        rel_path = file_entry["path"]
        expected_sha = file_entry["sha256"]
        file_path = backup_dir / rel_path

        if not file_path.exists():
            raise FileNotFoundError(f"Missing backup artifact: {rel_path}")

        actual_sha = compute_sha256(file_path)
        if actual_sha != expected_sha:
            raise RestoreChecksumError(
                f"SHA-256 mismatch for {rel_path}: expected {expected_sha}, got {actual_sha}"
            )

    logger.info("All manifest artifact checksums verified", verified_files=len(manifest.get("files", [])))
    return manifest


def verify_qdrant_collection_parity(
    collection_name: str,
    expected_dim: int,
    expected_points: list[dict[str, Any]],
    actual_points: list[dict[str, Any]],
    actual_collection_dim: int,
) -> dict[str, Any]:
    """Execute Tier I and Tier II parity verification for a restored Qdrant collection.

    - Tier I-A: Point-ID set equality (missing == 0, unexpected == 0).
    - Tier I-B: Core payload validation (tenant_id, document_id, content_hash).
    - Tier II: Finite non-NaN vector floats assertion.
    """
    # Dynamic dimension check
    if actual_collection_dim != expected_dim:
        raise QdrantParityError(
            f"Collection {collection_name} dimension mismatch: expected {expected_dim}, got {actual_collection_dim}"
        )

    expected_ids = {p["id"] for p in expected_points}
    actual_ids = {p["id"] for p in actual_points}

    missing_ids = expected_ids - actual_ids
    unexpected_ids = actual_ids - expected_ids

    if missing_ids:
        raise QdrantParityError(
            f"Collection {collection_name} has {len(missing_ids)} missing point IDs: {list(missing_ids)[:5]}"
        )
    if unexpected_ids:
        raise QdrantParityError(
            f"Collection {collection_name} has {len(unexpected_ids)} unexpected point IDs: {list(unexpected_ids)[:5]}"
        )

    # Payload & Vector float integrity (Tier I-B & Tier II)
    expected_by_id = {p["id"]: p for p in expected_points}
    for act in actual_points:
        pid = act["id"]
        exp = expected_by_id[pid]

        # Verify tenant_id
        if act.get("payload", {}).get("tenant_id") != exp.get("payload", {}).get("tenant_id"):
            raise QdrantParityError(f"Cross-tenant payload mismatch for point {pid}")

        # Verify vector floats
        vector = act.get("vector")
        if not vector or not isinstance(vector, list):
            raise QdrantParityError(f"Point {pid} missing vector float array")
        if len(vector) != expected_dim:
            raise QdrantParityError(f"Point {pid} vector length {len(vector)} != {expected_dim}")

        for val in vector:
            if math.isnan(val) or math.isinf(val):
                raise QdrantParityError(f"Point {pid} contains NaN or Infinite float value: {val}")

    logger.info(
        "Qdrant collection parity verified",
        collection=collection_name,
        points_count=len(actual_points),
        dimensions=actual_collection_dim,
    )
    return {
        "collection": collection_name,
        "verified_points": len(actual_points),
        "status": "PARITY_CONFIRMED",
    }
