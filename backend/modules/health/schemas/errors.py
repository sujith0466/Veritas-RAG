from enum import StrEnum

from backend.core.exceptions.base import RAGuardException


class HealthErrorCode(StrEnum):
    QUARANTINE_FAILED = "HLT_001"
    ANALYSIS_TIMEOUT = "HLT_002"


class HealthDomainException(RAGuardException):
    def __init__(self, message: str, error_code: str, detail: dict | None = None):
        super().__init__(message=message, error_code=error_code, detail=detail)
