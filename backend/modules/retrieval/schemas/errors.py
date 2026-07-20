"""Hybrid retrieval domain error taxonomy and exception models.

Provides standardized error classifications across sparse keyword matching,
dense vector retrieval, reciprocal rank fusion (`RRF`), and cross-encoder
reranking (`RET_001` to `RET_005`), with strict severity distinction (`RECOVERABLE` vs `FATAL`)
to drive Celery backoff retry policies.
"""

from enum import StrEnum
from http import HTTPStatus
from typing import Any

from backend.core.exceptions.base import RAGuardException


class ErrorSeverity(StrEnum):
    """Severity level determining background worker retry behavior."""

    RECOVERABLE = "RECOVERABLE"  # Transient connection issue or timeout; trigger backoff retry
    FATAL = "FATAL"              # Permanent query syntax, configuration, or pipeline error


class RetrievalErrorCode(StrEnum):
    """Retrieval domain error taxonomy (`RET_001` to `RET_005`)."""

    RET_001 = "RET_001"  # Invalid query string or parameters — FATAL
    RET_002 = "RET_002"  # Sparse index not found or uninitialized — FATAL
    RET_003 = "RET_003"  # Reranker connection timeout or throttle — RECOVERABLE
    RET_004 = "RET_004"  # Vector store unavailable during dense search — RECOVERABLE
    RET_005 = "RET_005"  # Fusion or deduplication pipeline error — FATAL
    RET_006 = "RET_006"  # FilterDSL validation error — FATAL
    RET_007 = "RET_007"  # Compression error — RECOVERABLE
    RET_008 = "RET_008"  # Tenant violation error — FATAL


ERROR_SEVERITY_MAP: dict[RetrievalErrorCode | str, ErrorSeverity] = {
    RetrievalErrorCode.RET_001: ErrorSeverity.FATAL,
    RetrievalErrorCode.RET_002: ErrorSeverity.FATAL,
    RetrievalErrorCode.RET_003: ErrorSeverity.RECOVERABLE,
    RetrievalErrorCode.RET_004: ErrorSeverity.RECOVERABLE,
    RetrievalErrorCode.RET_005: ErrorSeverity.FATAL,
    RetrievalErrorCode.RET_006: ErrorSeverity.FATAL,
    RetrievalErrorCode.RET_007: ErrorSeverity.RECOVERABLE,
    RetrievalErrorCode.RET_008: ErrorSeverity.FATAL,
}


def get_error_severity(code: RetrievalErrorCode | str) -> ErrorSeverity:
    """Resolve the error severity for a given code. Defaults to RECOVERABLE if unknown."""
    return ERROR_SEVERITY_MAP.get(code, ErrorSeverity.RECOVERABLE)


class RetrievalDomainException(RAGuardException):
    """Domain exception raised across the Hybrid Retrieval Engine subsystem (`ADR-005`)."""

    def __init__(
        self,
        code: RetrievalErrorCode | str,
        message: str,
        detail: dict[str, Any] | None = None,
        severity: ErrorSeverity | None = None,
    ) -> None:
        code_str = (
            code
            if isinstance(code, RetrievalErrorCode)
            else (
                RetrievalErrorCode(code)
                if code in RetrievalErrorCode._value2member_map_
                else str(code)
            )
        )
        self.code = code_str
        self.severity = severity or get_error_severity(self.code)

        status_code = HTTPStatus.INTERNAL_SERVER_ERROR
        if str(code_str) == "RET_001":
            status_code = HTTPStatus.BAD_REQUEST
        elif str(code_str) == "RET_002":
            status_code = HTTPStatus.NOT_FOUND
        elif str(code_str) in {"RET_003", "RET_004"}:
            status_code = HTTPStatus.SERVICE_UNAVAILABLE
        elif str(code_str) == "RET_005":
            status_code = HTTPStatus.UNPROCESSABLE_ENTITY
        elif str(code_str) == "RET_006":
            status_code = HTTPStatus.BAD_REQUEST
        elif str(code_str) == "RET_007":
            status_code = HTTPStatus.OK # Soft failure
        elif str(code_str) == "RET_008":
            status_code = HTTPStatus.FORBIDDEN

        self.http_status = int(status_code)
        super().__init__(message=message, detail=detail, error_code=str(code_str))

    def to_dict(self) -> dict[str, Any]:
        """Serialise error to a plain dict structure for HTTP response details."""
        return {
            "code": self.code,
            "message": self.message,
            "detail": self.detail,
            "severity": getattr(self, "severity", ErrorSeverity.FATAL),
        }



class InvalidQueryError(RetrievalDomainException):
    """Raised when query string exceeds length constraints or is invalid (`RET_001`)."""

    def __init__(self, message: str, detail: dict[str, Any] | None = None) -> None:
        super().__init__(code=RetrievalErrorCode.RET_001, message=message, detail=detail)


class SparseIndexNotFoundError(RetrievalDomainException):
    """Raised when attempting sparse search against a missing BM25 index (`RET_002`)."""

    def __init__(self, message: str, detail: dict[str, Any] | None = None) -> None:
        super().__init__(code=RetrievalErrorCode.RET_002, message=message, detail=detail)


class RerankerTimeoutError(RetrievalDomainException):
    """Raised when cross-encoder reranker inference or API call times out (`RET_003`, RECOVERABLE)."""

    def __init__(self, message: str, detail: dict[str, Any] | None = None) -> None:
        super().__init__(
            code=RetrievalErrorCode.RET_003,
            message=message,
            detail=detail,
            severity=ErrorSeverity.RECOVERABLE,
        )


class VectorStoreUnavailableError(RetrievalDomainException):
    """Raised when Qdrant vector store connection fails during dense retrieval (`RET_004`, RECOVERABLE)."""

    def __init__(self, message: str, detail: dict[str, Any] | None = None) -> None:
        super().__init__(
            code=RetrievalErrorCode.RET_004,
            message=message,
            detail=detail,
            severity=ErrorSeverity.RECOVERABLE,
        )


class FusionPipelineError(RetrievalDomainException):
    """Raised when RRF rank fusion or deduplication encounters a pipeline error (`RET_005`)."""

    def __init__(self, message: str, detail: dict[str, Any] | None = None) -> None:
        super().__init__(code=RetrievalErrorCode.RET_005, message=message, detail=detail)


class CandidateDeduplicationError(RetrievalDomainException):
    """Raised when deduplication filtering fails during candidate merging (`RET_005`)."""

    def __init__(self, message: str, detail: dict[str, Any] | None = None) -> None:
        super().__init__(code=RetrievalErrorCode.RET_005, message=message, detail=detail)


class FilterDSLValidationError(RetrievalDomainException):
    """Raised when FilterDSL validation fails (`RET_006`)."""

    def __init__(self, message: str, detail: dict[str, Any] | None = None) -> None:
        super().__init__(code=RetrievalErrorCode.RET_006, message=message, detail=detail)


class CompressionError(RetrievalDomainException):
    """Raised when context compression fails (`RET_007`)."""

    def __init__(self, message: str, detail: dict[str, Any] | None = None) -> None:
        super().__init__(code=RetrievalErrorCode.RET_007, message=message, detail=detail)


class TenantViolationError(RetrievalDomainException):
    """Raised when tenant isolation is violated (`RET_008`)."""

    def __init__(self, message: str, detail: dict[str, Any] | None = None) -> None:
        super().__init__(code=RetrievalErrorCode.RET_008, message=message, detail=detail)


