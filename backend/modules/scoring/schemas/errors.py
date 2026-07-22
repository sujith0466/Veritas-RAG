from enum import StrEnum

from backend.core.exceptions.base import RAGuardException


class ScoringErrorCode(StrEnum):
    SCORING_FAILED = "SCR_001"
    GATEWAY_TIMEOUT = "SCR_002"
    PIPELINE_ABORTED = "SCR_003"


class ScoringDomainException(RAGuardException):
    """Base exception for scoring domain."""

    def __init__(self, message: str, error_code: str, detail: dict | None = None):
        super().__init__(message=message, error_code=error_code, detail=detail)


class ScoringFailed(ScoringDomainException):
    def __init__(
        self, message: str = "Reliability scoring failed", detail: dict | None = None
    ):
        super().__init__(
            message=message, error_code=ScoringErrorCode.SCORING_FAILED, detail=detail
        )


class GatewayTimeout(ScoringDomainException):
    def __init__(
        self, message: str = "Execution gateway timed out", detail: dict | None = None
    ):
        super().__init__(
            message=message, error_code=ScoringErrorCode.GATEWAY_TIMEOUT, detail=detail
        )


class PipelineAborted(ScoringDomainException):
    def __init__(
        self,
        message: str = "Pipeline aborted by retry or confidence engine",
        detail: dict | None = None,
    ):
        super().__init__(
            message=message, error_code=ScoringErrorCode.PIPELINE_ABORTED, detail=detail
        )
