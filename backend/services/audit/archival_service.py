"""Audit Log WORM Archival & Cryptographic Tamper-Detection Engine (F15.7).

Provides:
1. Canonical serialization of immutable audit log records.
2. Cryptographic SHA-256 chained hashing and root integrity calculation.
3. Manifest generation with tamper-evident checksums.
4. Deterministic verification and tamper detection algorithms.
5. Strict multi-tenant isolation barriers during archival packaging.
"""

from collections.abc import Sequence
from dataclasses import asdict, dataclass
import datetime
import hashlib
import json
from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.entities.audit_log import AuditLog


class TamperDetectedError(Exception):
    """Raised when an audit archive fails cryptographic integrity verification."""

    def __init__(self, message: str, record_index: int | None = None, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.record_index = record_index
        self.details = details or {}


@dataclass(frozen=True)
class CanonicalAuditRecord:
    """Canonical representation of an audit log entry for deterministic hashing."""

    id: str
    created_at: str
    tenant_id: str | None
    action: str
    user_id: str | None
    resource_type: str | None
    resource_id: str | None
    details_json: str
    status: str
    record_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ArchiveManifest:
    """Tamper-evident manifest containing integrity metadata for an audit archive."""

    archive_id: str
    tenant_id: str
    period_start: str
    period_end: str
    record_count: int
    algorithm: str
    root_hash: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VerificationResult:
    """Verification outcome detailing archive integrity."""

    is_valid: bool
    record_count: int
    root_hash: str
    error_message: str | None = None
    mismatched_index: int | None = None


class AuditLogArchivalService:
    """Service governing immutable audit log archival, hashing, and tamper verification."""

    GENESIS_HASH = "0000000000000000000000000000000000000000000000000000000000000000"
    HASH_ALGORITHM = "SHA256-CHAIN-v1"

    @classmethod
    def compute_record_hash(
        cls,
        record_id: str,
        created_at_iso: str,
        tenant_id: str | None,
        action: str,
        user_id: str | None,
        resource_type: str | None,
        resource_id: str | None,
        details: dict[str, Any] | None,
        status: str,
    ) -> tuple[str, str]:
        """Compute canonical SHA-256 hash for a single audit record.

        Returns (record_hash, canonical_details_json).
        """
        canonical_details = json.dumps(details or {}, sort_keys=True, separators=(",", ":"))

        # Strict delimiter-separated canonical payload
        payload_elements = [
            record_id,
            created_at_iso,
            tenant_id or "",
            action,
            user_id or "",
            resource_type or "",
            resource_id or "",
            canonical_details,
            status,
        ]
        canonical_string = "|".join(payload_elements)
        record_hash = hashlib.sha256(canonical_string.encode("utf-8")).hexdigest()
        return record_hash, canonical_details

    @classmethod
    def serialize_record(cls, log: AuditLog) -> CanonicalAuditRecord:
        """Convert an ORM AuditLog entity into a canonical hashed record."""
        created_at_iso = log.created_at.isoformat() if isinstance(log.created_at, datetime.datetime) else str(log.created_at)
        rec_id = str(log.id)
        tenant_id_str = str(log.tenant_id) if log.tenant_id else None
        user_id_str = str(log.user_id) if log.user_id else None

        record_hash, canonical_details = cls.compute_record_hash(
            record_id=rec_id,
            created_at_iso=created_at_iso,
            tenant_id=tenant_id_str,
            action=log.action,
            user_id=user_id_str,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            details=log.details,
            status=log.status,
        )

        return CanonicalAuditRecord(
            id=rec_id,
            created_at=created_at_iso,
            tenant_id=tenant_id_str,
            action=log.action,
            user_id=user_id_str,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            details_json=canonical_details,
            status=log.status,
            record_hash=record_hash,
        )

    @classmethod
    def build_archive_package(
        cls,
        records: Sequence[AuditLog],
        tenant_id: uuid.UUID,
        period_start: datetime.datetime,
        period_end: datetime.datetime,
    ) -> tuple[list[dict[str, Any]], ArchiveManifest]:
        """Transform audit logs into a verified, chained immutable archive package."""
        serialized_records: list[CanonicalAuditRecord] = []
        current_chain_hash = cls.GENESIS_HASH

        # Deterministic sort by created_at ascending, then id ascending
        sorted_logs = sorted(
            records,
            key=lambda r: (r.created_at.isoformat() if isinstance(r.created_at, datetime.datetime) else str(r.created_at), str(r.id)),
        )

        for log in sorted_logs:
            # Enforce strict tenant boundary check
            if log.tenant_id != tenant_id:
                raise ValueError(f"Cross-tenant pollution detected: log tenant {log.tenant_id} != expected {tenant_id}")

            canonical = cls.serialize_record(log)
            serialized_records.append(canonical)

            # Chained hash accumulation: H_i = SHA256(H_{i-1} + record_hash_i)
            chain_payload = f"{current_chain_hash}:{canonical.record_hash}"
            current_chain_hash = hashlib.sha256(chain_payload.encode("utf-8")).hexdigest()

        manifest = ArchiveManifest(
            archive_id=str(uuid.uuid4()),
            tenant_id=str(tenant_id),
            period_start=period_start.isoformat(),
            period_end=period_end.isoformat(),
            record_count=len(serialized_records),
            algorithm=cls.HASH_ALGORITHM,
            root_hash=current_chain_hash,
            created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )

        return [rec.to_dict() for rec in serialized_records], manifest

    @classmethod
    def verify_archive_integrity(
        cls,
        records_data: list[dict[str, Any]],
        manifest: ArchiveManifest | dict[str, Any],
    ) -> VerificationResult:
        """Cryptographically verify an archive package against its integrity manifest.

        Detects:
        - Record field modification
        - Record insertion or deletion
        - Record re-ordering
        - Manifest root_hash tampering
        """
        if isinstance(manifest, dict):
            manifest_dict = manifest
            expected_count = manifest_dict.get("record_count", 0)
            expected_root = manifest_dict.get("root_hash", "")
            algorithm = manifest_dict.get("algorithm", "")
        else:
            expected_count = manifest.record_count
            expected_root = manifest.root_hash
            algorithm = manifest.algorithm

        if algorithm != cls.HASH_ALGORITHM:
            return VerificationResult(
                is_valid=False,
                record_count=len(records_data),
                root_hash="",
                error_message=f"Unsupported integrity algorithm: '{algorithm}'. Expected '{cls.HASH_ALGORITHM}'",
            )

        # 1. Verify record count
        if len(records_data) != expected_count:
            return VerificationResult(
                is_valid=False,
                record_count=len(records_data),
                root_hash="",
                error_message=f"Record count mismatch: manifest expected {expected_count}, but archive contains {len(records_data)}",
            )

        # 2. Verify individual record hashes and chain integrity
        current_chain_hash = cls.GENESIS_HASH

        for index, record_dict in enumerate(records_data):
            try:
                # Recalculate record hash independently
                details = json.loads(record_dict.get("details_json", "{}"))
                recomputed_hash, _ = cls.compute_record_hash(
                    record_id=record_dict["id"],
                    created_at_iso=record_dict["created_at"],
                    tenant_id=record_dict.get("tenant_id"),
                    action=record_dict["action"],
                    user_id=record_dict.get("user_id"),
                    resource_type=record_dict.get("resource_type"),
                    resource_id=record_dict.get("resource_id"),
                    details=details,
                    status=record_dict["status"],
                )

                if recomputed_hash != record_dict.get("record_hash"):
                    return VerificationResult(
                        is_valid=False,
                        record_count=len(records_data),
                        root_hash="",
                        error_message=(
                            f"Record tamper detected at index {index} (ID: {record_dict.get('id')}): "
                            f"computed hash '{recomputed_hash}' does not match stored '{record_dict.get('record_hash')}'"
                        ),
                        mismatched_index=index,
                    )

                # Accumulate chain hash
                chain_payload = f"{current_chain_hash}:{recomputed_hash}"
                current_chain_hash = hashlib.sha256(chain_payload.encode("utf-8")).hexdigest()

            except Exception as e:
                return VerificationResult(
                    is_valid=False,
                    record_count=len(records_data),
                    root_hash="",
                    error_message=f"Corrupted record format at index {index}: {str(e)}",
                    mismatched_index=index,
                )

        # 3. Verify final chain hash matches manifest root hash
        if current_chain_hash != expected_root:
            return VerificationResult(
                is_valid=False,
                record_count=len(records_data),
                root_hash=current_chain_hash,
                error_message=(
                    f"Root integrity mismatch: computed chain hash '{current_chain_hash}' "
                    f"does not match manifest root '{expected_root}'"
                ),
            )

        return VerificationResult(
            is_valid=True,
            record_count=len(records_data),
            root_hash=current_chain_hash,
        )

    @classmethod
    async def query_tenant_logs_for_archival(
        cls,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        start_time: datetime.datetime,
        end_time: datetime.datetime,
    ) -> Sequence[AuditLog]:
        """Fetch immutable audit records for a specific tenant in a time window."""
        stmt = (
            select(AuditLog)
            .where(
                AuditLog.tenant_id == tenant_id,
                AuditLog.created_at >= start_time,
                AuditLog.created_at < end_time,
            )
            .order_by(AuditLog.created_at.asc(), AuditLog.id.asc())
        )
        result = await session.execute(stmt)
        return result.scalars().all()
