"""Knowledge Health Module Error Taxonomy (`ADR-005`, `KHL_001` to `KHL_005`).

Defines structured exceptions for scan jobs, count parity discrepancies, two-phase purges, and model drift.
"""

from http import HTTPStatus
from typing import Any, Dict, Optional
from backend.core.exceptions import RAGuardException


class KnowledgeHealthDomainException(RAGuardException):
    """Base exception for all Knowledge Health & Lifecycle module failures."""

    def __init__(
        self,
        code: str,
        message: str,
        is_recoverable: bool = True,
        detail: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.code = code
        self.is_recoverable = is_recoverable
        status_code = HTTPStatus.INTERNAL_SERVER_ERROR
        if code == "KHL_001":
            status_code = HTTPStatus.BAD_REQUEST
        elif code in {"KHL_002", "KHL_004"}:
            status_code = HTTPStatus.CONFLICT
        elif code == "KHL_003":
            status_code = HTTPStatus.SERVICE_UNAVAILABLE
        elif code == "KHL_005":
            status_code = HTTPStatus.INTERNAL_SERVER_ERROR

        self.http_status = int(status_code)
        super().__init__(
            message=message,
            detail=detail or {},
            error_code=code,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize exception to standard API error response structure."""
        return {
            "success": False,
            "error": {
                "code": self.code,
                "message": self.message,
                "detail": self.detail,
            },
        }


class InvalidScanTypeError(KnowledgeHealthDomainException):
    """KHL_001: Raised when an invalid health scan type is requested."""

    def __init__(self, tenant_id: str, scan_type: str, detail: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(
            code="KHL_001",
            message=f"Invalid or unsupported scan type '{scan_type}' requested for tenant '{tenant_id}'.",
            is_recoverable=False,
            detail={"tenant_id": tenant_id, "scan_type": scan_type, **(detail or {})},
        )


class ParityMismatchError(KnowledgeHealthDomainException):
    """KHL_002: Raised when 1:1 count parity between PostgreSQL chunks and Qdrant points fails."""

    def __init__(self, tenant_id: str, pg_count: int, qdrant_count: int, detail: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(
            code="KHL_002",
            message=f"Count parity mismatch detected for tenant '{tenant_id}': PostgreSQL has {pg_count} chunks but Qdrant has {qdrant_count} points.",
            is_recoverable=True,
            detail={"tenant_id": tenant_id, "pg_count": pg_count, "qdrant_count": qdrant_count, **(detail or {})},
        )


class PurgeSynchronizationError(KnowledgeHealthDomainException):
    """KHL_003: Raised when Qdrant vector deletion fails during two-phase purge, preserving DB row in soft-deleted state."""

    def __init__(self, tenant_id: str, document_id: str, reason: str, detail: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(
            code="KHL_003",
            message=f"Two-phase purge synchronization failed for document '{document_id}' in tenant '{tenant_id}': {reason}",
            is_recoverable=True,
            detail={"tenant_id": tenant_id, "document_id": document_id, "reason": reason, **(detail or {})},
        )


class ModelRotationConflictError(KnowledgeHealthDomainException):
    """KHL_004: Raised when a model rotation is requested while another migration job is active."""

    def __init__(self, tenant_id: str, active_job_id: str, detail: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(
            code="KHL_004",
            message=f"Model rotation conflict for tenant '{tenant_id}': migration job '{active_job_id}' is already active.",
            is_recoverable=False,
            detail={"tenant_id": tenant_id, "active_job_id": active_job_id, **(detail or {})},
        )


class StaleEmbeddingScanError(KnowledgeHealthDomainException):
    """KHL_005: Raised when an error occurs while scanning or re-indexing stale embeddings."""

    def __init__(self, tenant_id: str, reason: str, detail: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(
            code="KHL_005",
            message=f"Stale embedding scan failure for tenant '{tenant_id}': {reason}",
            is_recoverable=True,
            detail={"tenant_id": tenant_id, "reason": reason, **(detail or {})},
        )
