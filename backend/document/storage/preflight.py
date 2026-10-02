"""Storage Pre-Flight Validator (`StoragePreflightValidator`).

Validates physical availability, readability, key sanitization, tenant namespace isolation,
and historical path anomalies (e.g. Windows D:\\ vs container volume paths) before worker
extraction begins, preventing uncontrolled worker crashes.
"""

from dataclasses import dataclass
import os
from pathlib import Path
import re
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class PreflightResult:
    """Outcome of a storage pre-flight validation check."""

    is_valid: bool
    storage_provider: str
    bucket_or_container: str
    object_key: str
    resolved_path: str | None = None
    file_size_bytes: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    anomaly_type: str | None = None


class StoragePreflightValidator:
    """Pre-flight check executing prior to worker extraction."""

    CONTAINER_ROOT = Path("/app/data/storage")
    HOST_FALLBACK_ROOT = Path("D:/app/data/storage")

    @classmethod
    def validate(
        cls,
        storage_object: Any,
        expected_tenant_id: str | None = None,
    ) -> PreflightResult:
        """Execute comprehensive pre-flight verification on a StorageObject.

        Args:
            storage_object: StorageObject ORM entity or DTO with attributes:
                            `storage_provider`, `bucket_or_container`, `object_key`, `size_bytes`.
            expected_tenant_id: Optional tenant UUID string to verify namespace isolation.
        """
        provider = getattr(storage_object, "storage_provider", "local") or "local"
        bucket = getattr(storage_object, "bucket_or_container", "") or ""
        object_key = getattr(storage_object, "object_key", "") or ""
        expected_size = getattr(storage_object, "size_bytes", None)

        # 1. Malformed Key & Path Traversal Check
        if not object_key or "\0" in object_key:
            return PreflightResult(
                is_valid=False,
                storage_provider=provider,
                bucket_or_container=bucket,
                object_key=object_key,
                error_code="MALFORMED_STORAGE_KEY",
                error_message="Storage object key is empty or contains null bytes.",
            )

        normalized_key = object_key.replace("\\", "/").strip()
        if ".." in normalized_key.split("/"):
            return PreflightResult(
                is_valid=False,
                storage_provider=provider,
                bucket_or_container=bucket,
                object_key=object_key,
                error_code="PATH_TRAVERSAL_DETECTED",
                error_message="Storage key contains path traversal components ('..').",
            )

        # 2. Tenant Isolation Check
        if expected_tenant_id:
            normalized_expected = str(expected_tenant_id).strip().lower()
            # If the object_key begins with a UUID-like path segment, ensure it matches expected_tenant_id
            parts = normalized_key.lstrip("/").split("/")
            if parts and len(parts[0]) == 36 and "-" in parts[0]:
                key_tenant = parts[0].lower()
                if key_tenant != normalized_expected:
                    logger.warning(
                        "Tenant isolation violation in storage key",
                        expected_tenant=normalized_expected,
                        key_tenant=key_tenant,
                        object_key=object_key,
                    )
                    return PreflightResult(
                        is_valid=False,
                        storage_provider=provider,
                        bucket_or_container=bucket,
                        object_key=object_key,
                        error_code="TENANT_ISOLATION_VIOLATION",
                        error_message=f"Storage object does not belong to tenant '{expected_tenant_id}'.",
                    )

        # 3. Detect Historical Path Anomalies (Windows host path vs Container path)
        anomaly_type = None
        if r"D:\app\data\storage" in bucket or r"d:\app\data\storage" in bucket or (bucket.startswith("D:") and "app" in bucket):
            anomaly_type = "HISTORICAL_WINDOWS_PATH"

        # 4. Resolve Physical File Candidate Paths
        candidate_paths: list[Path] = []
        clean_key = normalized_key.lstrip("/")

        # Candidate A: Using the recorded bucket_or_container directly if available
        if bucket:
            try:
                candidate_paths.append((Path(bucket) / clean_key).resolve())
            except Exception:
                pass

        # Candidate B: Standard container root
        candidate_paths.append((cls.CONTAINER_ROOT / clean_key).resolve())

        # Candidate C: Host fallback root (if on local Windows machine)
        candidate_paths.append((cls.HOST_FALLBACK_ROOT / clean_key).resolve())

        # 5. Check Physical Existence
        resolved_file: Path | None = None
        for candidate in candidate_paths:
            try:
                if candidate.exists() and candidate.is_file():
                    resolved_file = candidate
                    break
            except Exception:
                continue

        if not resolved_file:
            logger.warning(
                "Physical storage artifact missing",
                object_key=object_key,
                bucket=bucket,
                anomaly=anomaly_type,
            )
            return PreflightResult(
                is_valid=False,
                storage_provider=provider,
                bucket_or_container=bucket,
                object_key=object_key,
                error_code="STORAGE_OBJECT_NOT_FOUND",
                error_message=f"Physical storage artifact '{object_key}' does not exist on storage volume.",
                anomaly_type=anomaly_type,
            )

        # 6. Check Physical Readability
        try:
            with open(resolved_file, "rb") as f:
                f.read(1)
            actual_size = resolved_file.stat().st_size
        except PermissionError as perm_err:
            return PreflightResult(
                is_valid=False,
                storage_provider=provider,
                bucket_or_container=bucket,
                object_key=object_key,
                resolved_path=str(resolved_file),
                error_code="OBJECT_UNREADABLE",
                error_message=f"Permission denied reading storage object: {perm_err}",
                anomaly_type=anomaly_type,
            )
        except OSError as os_err:
            return PreflightResult(
                is_valid=False,
                storage_provider=provider,
                bucket_or_container=bucket,
                object_key=object_key,
                resolved_path=str(resolved_file),
                error_code="OBJECT_UNREADABLE",
                error_message=f"I/O error reading storage object: {os_err}",
                anomaly_type=anomaly_type,
            )

        # 7. Success
        return PreflightResult(
            is_valid=True,
            storage_provider=provider,
            bucket_or_container=bucket,
            object_key=object_key,
            resolved_path=str(resolved_file),
            file_size_bytes=actual_size,
            anomaly_type=anomaly_type,
        )
