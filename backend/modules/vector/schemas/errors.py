"""Vector storage domain error taxonomy and exception models.

Provides standardized error classifications across Qdrant collection administration,
payload index verification, and point batch upserts with strict severity distinction
(`RECOVERABLE vs FATAL`) to drive Celery backoff retry policies (`ADR-M3-002`).
"""

from enum import StrEnum
from http import HTTPStatus
from typing import Any

from backend.core.exceptions.base import RAGuardException


class ErrorSeverity(StrEnum):
    """Severity level determining background worker retry behavior."""

    RECOVERABLE = "RECOVERABLE"  # Transient connection issue or timeout; trigger backoff retry
    FATAL = "FATAL"              # Permanent schema, dimension, or collection configuration error


class VectorErrorCode(StrEnum):
    """Vector storage domain error taxonomy (`VEC_001` to `VEC_005`)."""

    VEC_001 = "VEC_001"  # Invalid or missing required payload schema properties — FATAL
    VEC_002 = "VEC_002"  # Target vector collection not found — FATAL
    VEC_003 = "VEC_003"  # Qdrant connection error or gRPC transport failure — RECOVERABLE
    VEC_004 = "VEC_004"  # Vector dimension mismatch with collection configuration — FATAL
    VEC_005 = "VEC_005"  # Indexing synchronization timeout — RECOVERABLE


ERROR_SEVERITY_MAP: dict[VectorErrorCode | str, ErrorSeverity] = {
    VectorErrorCode.VEC_001: ErrorSeverity.FATAL,
    VectorErrorCode.VEC_002: ErrorSeverity.FATAL,
    VectorErrorCode.VEC_003: ErrorSeverity.RECOVERABLE,
    VectorErrorCode.VEC_004: ErrorSeverity.FATAL,
    VectorErrorCode.VEC_005: ErrorSeverity.RECOVERABLE,
}


def get_error_severity(code: VectorErrorCode | str) -> ErrorSeverity:
    """Resolve the error severity for a given code. Defaults to RECOVERABLE if unknown."""
    return ERROR_SEVERITY_MAP.get(code, ErrorSeverity.RECOVERABLE)


class VectorDomainException(RAGuardException):
    """Domain exception raised across the Vector Storage Foundation subsystem (`ADR-005`)."""

    def __init__(
        self,
        code: VectorErrorCode | str,
        message: str,
        detail: dict[str, Any] | None = None,
        severity: ErrorSeverity | None = None,
    ) -> None:
        code_str = (
            code
            if isinstance(code, VectorErrorCode)
            else (
                VectorErrorCode(code)
                if code in VectorErrorCode._value2member_map_
                else str(code)
            )
        )
        self.code = code_str
        self.severity = severity or get_error_severity(self.code)

        status_code = HTTPStatus.INTERNAL_SERVER_ERROR
        if str(code_str) in {"VEC_001", "VEC_004"}:
            status_code = HTTPStatus.BAD_REQUEST
        elif str(code_str) == "VEC_002":
            status_code = HTTPStatus.NOT_FOUND
        elif str(code_str) == "VEC_003":
            status_code = HTTPStatus.SERVICE_UNAVAILABLE
        elif str(code_str) == "VEC_005":
            status_code = HTTPStatus.GATEWAY_TIMEOUT

        self.http_status = int(status_code)
        super().__init__(message=message, detail=detail, error_code=str(code_str))


class InvalidPayloadSchemaError(VectorDomainException):
    """Raised when point payload properties violate strict tenant filtering schema (`VEC_001`)."""

    def __init__(self, message: str, detail: dict[str, Any] | None = None) -> None:
        super().__init__(code=VectorErrorCode.VEC_001, message=message, detail=detail)


class CollectionNotFoundError(VectorDomainException):
    """Raised when attempting to query or upsert into a non-existent Qdrant collection (`VEC_002`)."""

    def __init__(self, message: str, detail: dict[str, Any] | None = None) -> None:
        super().__init__(code=VectorErrorCode.VEC_002, message=message, detail=detail)


class QdrantConnectionError(VectorDomainException):
    """Raised when gRPC or REST connection to Qdrant cluster fails (`VEC_003`, RECOVERABLE)."""

    def __init__(self, message: str, detail: dict[str, Any] | None = None) -> None:
        super().__init__(
            code=VectorErrorCode.VEC_003,
            message=message,
            detail=detail,
            severity=ErrorSeverity.RECOVERABLE,
        )


class DimensionMismatchError(VectorDomainException):
    """Raised when embedding vector dimension does not match collection configuration (`VEC_004`)."""

    def __init__(self, message: str, detail: dict[str, Any] | None = None) -> None:
        super().__init__(code=VectorErrorCode.VEC_004, message=message, detail=detail)


class IndexSyncTimeoutError(VectorDomainException):
    """Raised when asynchronous indexing operation exceeds timeout threshold (`VEC_005`, RECOVERABLE)."""

    def __init__(self, message: str, detail: dict[str, Any] | None = None) -> None:
        super().__init__(
            code=VectorErrorCode.VEC_005,
            message=message,
            detail=detail,
            severity=ErrorSeverity.RECOVERABLE,
        )
