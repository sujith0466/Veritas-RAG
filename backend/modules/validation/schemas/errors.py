from enum import StrEnum

from backend.core.exceptions.base import RAGuardException


class ValidationErrorCode(StrEnum):
    UNSUPPORTED_CLAIM = "VAL_001"
    INVALID_CITATION = "VAL_002"
    NLI_EVALUATION_FAILED = "VAL_003"
    ORCHESTRATION_FAILED = "VAL_004"


class ValidationDomainException(RAGuardException):
    def __init__(self, message: str, error_code: str, detail: dict | None = None):
        super().__init__(message=message, error_code=error_code, detail=detail)


class UnsupportedClaimError(ValidationDomainException):
    def __init__(
        self,
        message: str = "Claim lacks supporting evidence",
        detail: dict | None = None,
    ):
        super().__init__(
            message=message,
            error_code=ValidationErrorCode.UNSUPPORTED_CLAIM,
            detail=detail,
        )


class InvalidCitationError(ValidationDomainException):
    def __init__(
        self,
        message: str = "Citation reference is invalid or missing",
        detail: dict | None = None,
    ):
        super().__init__(
            message=message,
            error_code=ValidationErrorCode.INVALID_CITATION,
            detail=detail,
        )
