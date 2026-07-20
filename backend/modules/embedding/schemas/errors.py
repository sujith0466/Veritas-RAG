"""Embedding domain error taxonomy and exception models.

Provides standardized error classifications across batch vectorization, token quota checks,
and provider API invocations with strict severity distinction (RECOVERABLE vs FATAL)
to drive Celery jittered exponential backoff retry policy (`ADR-M2-002`).
"""

from enum import StrEnum
from http import HTTPStatus
from typing import Any

from backend.core.exceptions.base import RAGuardException


class ErrorSeverity(StrEnum):
    """Severity level determining background worker retry behavior."""

    RECOVERABLE = "RECOVERABLE"  # Transient rate limit (429) or timeout (5xx); trigger exponential backoff retry
    FATAL = "FATAL"              # Permanent quota/auth/input error; transition immediately to FAILED


class EmbeddingErrorCode(StrEnum):
    """Embedding domain error taxonomy (`EMB_001` to `EMB_005`)."""

    EMB_001 = "EMB_001"  # Invalid input or empty chunk batch — FATAL
    EMB_002 = "EMB_002"  # Token quota exceeded for tenant namespace — FATAL
    EMB_003 = "EMB_003"  # Provider rate limit exceeded (HTTP 429) — RECOVERABLE
    EMB_004 = "EMB_004"  # Provider network timeout or upstream 5xx failure — RECOVERABLE
    EMB_005 = "EMB_005"  # Provider API key invalid or authentication failure — FATAL


ERROR_SEVERITY_MAP: dict[EmbeddingErrorCode | str, ErrorSeverity] = {
    EmbeddingErrorCode.EMB_001: ErrorSeverity.FATAL,
    EmbeddingErrorCode.EMB_002: ErrorSeverity.FATAL,
    EmbeddingErrorCode.EMB_003: ErrorSeverity.RECOVERABLE,
    EmbeddingErrorCode.EMB_004: ErrorSeverity.RECOVERABLE,
    EmbeddingErrorCode.EMB_005: ErrorSeverity.FATAL,
}


def get_error_severity(code: EmbeddingErrorCode | str) -> ErrorSeverity:
    """Resolve the error severity for a given code. Defaults to RECOVERABLE if unknown."""
    return ERROR_SEVERITY_MAP.get(code, ErrorSeverity.RECOVERABLE)


class EmbeddingDomainException(RAGuardException):
    """Domain exception raised across the Embedding Pipeline subsystem (`ADR-005`)."""

    def __init__(
        self,
        code: EmbeddingErrorCode | str,
        message: str,
        detail: dict[str, Any] | None = None,
        severity: ErrorSeverity | None = None,
    ) -> None:
        code_str = code if isinstance(code, EmbeddingErrorCode) else EmbeddingErrorCode(code) if code in EmbeddingErrorCode._value2member_map_ else str(code)
        self.code = code_str
        self.severity = severity or get_error_severity(self.code)

        status_code = HTTPStatus.INTERNAL_SERVER_ERROR
        if str(code_str) == "EMB_001":
            status_code = HTTPStatus.BAD_REQUEST
        elif str(code_str) in {"EMB_002", "EMB_003"}:
            status_code = HTTPStatus.TOO_MANY_REQUESTS
        elif str(code_str) == "EMB_004":
            status_code = HTTPStatus.GATEWAY_TIMEOUT
        elif str(code_str) == "EMB_005":
            status_code = HTTPStatus.UNAUTHORIZED

        self.http_status = int(status_code)
        super().__init__(message=message, detail=detail, error_code=str(code_str))


class InvalidInputError(EmbeddingDomainException):
    """Raised when batch input is invalid or chunk IDs are missing (`EMB_001`)."""

    def __init__(self, message: str, detail: dict[str, Any] | None = None) -> None:
        super().__init__(code=EmbeddingErrorCode.EMB_001, message=message, detail=detail)


class TokenQuotaExceededError(EmbeddingDomainException):
    """Raised when a tenant exceeds their allocated monthly token budget (`EMB_002`)."""

    def __init__(self, message: str, detail: dict[str, Any] | None = None) -> None:
        super().__init__(code=EmbeddingErrorCode.EMB_002, message=message, detail=detail)


class RateLimitExceededError(EmbeddingDomainException):
    """EMB_003: Provider HTTP 429 throttling / rate limit hit (`RECOVERABLE=True`)."""

    def __init__(self, message: str, detail: dict[str, Any] | None = None) -> None:
        super().__init__(message=message, code=EmbeddingErrorCode.EMB_003, severity=ErrorSeverity.RECOVERABLE, detail=detail)


ProviderRateLimitError = RateLimitExceededError


class ProviderTimeoutError(EmbeddingDomainException):
    """Raised when network timeout or upstream 5xx server error occurs (`EMB_004`)."""

    def __init__(self, message: str, detail: dict[str, Any] | None = None) -> None:
        super().__init__(code=EmbeddingErrorCode.EMB_004, message=message, detail=detail)


class ProviderAuthenticationError(EmbeddingDomainException):
    """Raised when provider API key is missing, invalid, or expired (`EMB_005`)."""

    def __init__(self, message: str, detail: dict[str, Any] | None = None) -> None:
        super().__init__(code=EmbeddingErrorCode.EMB_005, message=message, detail=detail)
