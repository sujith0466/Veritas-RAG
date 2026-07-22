from enum import StrEnum

from backend.core.exceptions.base import RAGuardException


class ConfidenceErrorCode(StrEnum):
    INVALID_EVIDENCE = "CNF_001"
    CONTRADICTION_DETECTION_FAILED = "CNF_002"
    SCORING_FAILED = "CNF_003"


class ConfidenceDomainException(RAGuardException):
    """Base exception for confidence domain."""

    def __init__(self, message: str, error_code: str, detail: dict | None = None):
        super().__init__(message=message, error_code=error_code, detail=detail)


class InvalidEvidencePayload(ConfidenceDomainException):
    def __init__(
        self,
        message: str = "Invalid evidence payload provided for confidence scoring",
        detail: dict | None = None,
    ):
        super().__init__(
            message=message,
            error_code=ConfidenceErrorCode.INVALID_EVIDENCE,
            detail=detail,
        )


class ContradictionDetectionFailed(ConfidenceDomainException):
    def __init__(
        self,
        message: str = "Failed to detect contradictions in evidence",
        detail: dict | None = None,
    ):
        super().__init__(
            message=message,
            error_code=ConfidenceErrorCode.CONTRADICTION_DETECTION_FAILED,
            detail=detail,
        )


class ConfidenceScoringFailed(ConfidenceDomainException):
    def __init__(
        self,
        message: str = "Failed to compute confidence score",
        detail: dict | None = None,
    ):
        super().__init__(
            message=message,
            error_code=ConfidenceErrorCode.SCORING_FAILED,
            detail=detail,
        )
