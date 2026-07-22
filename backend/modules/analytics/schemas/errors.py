"""Error taxonomy for the Query Analytics domain (`ANL_001` to `ANL_003`)."""

from enum import StrEnum

from backend.core.exceptions.base import RAGuardException


class AnalyticsErrorCode(StrEnum):
    RECORD_NOT_FOUND = "ANL_001"
    INVALID_DATE_RANGE = "ANL_002"
    AGGREGATION_FAILED = "ANL_003"


class AnalyticsDomainException(RAGuardException):
    """Base exception for query analytics domain."""

    def __init__(self, message: str, error_code: str, detail: dict | None = None):
        super().__init__(message=message, error_code=error_code, detail=detail)


class RecordNotFound(AnalyticsDomainException):
    def __init__(
        self,
        message: str = "Analytics query record not found",
        detail: dict | None = None,
    ):
        super().__init__(
            message=message,
            error_code=AnalyticsErrorCode.RECORD_NOT_FOUND,
            detail=detail,
        )


class InvalidDateRange(AnalyticsDomainException):
    def __init__(
        self,
        message: str = "Invalid date range or interval specified for query analytics",
        detail: dict | None = None,
    ):
        super().__init__(
            message=message,
            error_code=AnalyticsErrorCode.INVALID_DATE_RANGE,
            detail=detail,
        )


class AggregationFailed(AnalyticsDomainException):
    def __init__(
        self,
        message: str = "Failed to aggregate query analytics metrics",
        detail: dict | None = None,
    ):
        super().__init__(
            message=message,
            error_code=AnalyticsErrorCode.AGGREGATION_FAILED,
            detail=detail,
        )


class QuotaExceededError(RAGuardException):
    def __init__(self, message: str):
        super().__init__(message=message, error_code="ANA_QTA_001")


class InvalidPricingModelError(RAGuardException):
    def __init__(self, message: str):
        super().__init__(message=message, error_code="ANA_PRC_001")
