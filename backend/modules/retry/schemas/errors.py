from enum import StrEnum
from backend.core.exceptions.base import RAGuardException


class RetryErrorCode(StrEnum):
    MAX_RETRIES_EXCEEDED = "RTY_001"
    NON_MONOTONIC_IMPROVEMENT = "RTY_002"
    INVALID_STATE_TRANSITION = "RTY_003"


class RetryDomainException(RAGuardException):
    """Base exception for retry domain."""
    def __init__(self, message: str, error_code: str, detail: dict | None = None):
        super().__init__(message=message, error_code=error_code, detail=detail)


class MaxRetriesExceeded(RetryDomainException):
    def __init__(self, message: str = "Maximum retries exceeded", detail: dict | None = None):
        super().__init__(message=message, error_code=RetryErrorCode.MAX_RETRIES_EXCEEDED, detail=detail)


class NonMonotonicImprovement(RetryDomainException):
    def __init__(self, message: str = "Retry did not improve confidence score", detail: dict | None = None):
        super().__init__(message=message, error_code=RetryErrorCode.NON_MONOTONIC_IMPROVEMENT, detail=detail)


class InvalidStateTransition(RetryDomainException):
    def __init__(self, message: str = "Invalid state transition requested", detail: dict | None = None):
        super().__init__(message=message, error_code=RetryErrorCode.INVALID_STATE_TRANSITION, detail=detail)
