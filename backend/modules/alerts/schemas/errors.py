from enum import StrEnum
from backend.core.exceptions.base import RAGuardException

class AlertErrorCode(StrEnum):
    CHANNEL_DELIVERY_FAILED = "ALT_001"
    RULE_EVALUATION_ERROR = "ALT_002"

class AlertDomainException(RAGuardException):
    def __init__(self, message: str, error_code: str, detail: dict | None = None):
        super().__init__(message=message, error_code=error_code, detail=detail)
