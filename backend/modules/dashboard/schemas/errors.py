from enum import StrEnum
from backend.core.exceptions.base import RAGuardException

class DashboardErrorCode(StrEnum):
    EXPORT_FAILED = "DASH_001"
    INVALID_WINDOW = "DASH_002"
    CACHE_ERROR = "DASH_003"

class DashboardDomainException(RAGuardException):
    def __init__(self, message: str, error_code: str, detail: dict | None = None):
        super().__init__(message=message, error_code=error_code, detail=detail)
