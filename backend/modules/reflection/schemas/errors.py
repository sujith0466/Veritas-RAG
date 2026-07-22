from enum import StrEnum

from backend.core.exceptions.base import RAGuardException


class ReflectionErrorCode(StrEnum):
    CLAIM_EXTRACTION_FAILED = "REF_001"
    VALIDATION_FAILED = "REF_002"
    REFLECTION_TIMEOUT = "REF_003"


class ReflectionDomainException(RAGuardException):
    """Base exception for reflection domain."""

    def __init__(self, message: str, error_code: str, detail: dict | None = None):
        super().__init__(message=message, error_code=error_code, detail=detail)


class ClaimExtractionFailed(ReflectionDomainException):
    def __init__(
        self,
        message: str = "Failed to extract claims from answer",
        detail: dict | None = None,
    ):
        super().__init__(
            message=message,
            error_code=ReflectionErrorCode.CLAIM_EXTRACTION_FAILED,
            detail=detail,
        )


class ValidationFailed(ReflectionDomainException):
    def __init__(
        self, message: str = "Claim validation failed", detail: dict | None = None
    ):
        super().__init__(
            message=message,
            error_code=ReflectionErrorCode.VALIDATION_FAILED,
            detail=detail,
        )


class ReflectionTimeout(ReflectionDomainException):
    def __init__(
        self, message: str = "Reflection engine timed out", detail: dict | None = None
    ):
        super().__init__(
            message=message,
            error_code=ReflectionErrorCode.REFLECTION_TIMEOUT,
            detail=detail,
        )


class ReflectionEvaluationFailed(ReflectionDomainException):
    def __init__(
        self, message: str = "Reflection evaluation failed", detail: dict | None = None
    ):
        super().__init__(message=message, error_code="REF_004", detail=detail)


class ContradictionDetectedError(ReflectionDomainException):
    def __init__(
        self,
        message: str = "Logical contradiction detected in claims",
        detail: dict | None = None,
    ):
        super().__init__(message=message, error_code="REF_005", detail=detail)
