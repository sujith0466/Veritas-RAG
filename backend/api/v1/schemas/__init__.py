"""RAGuard AI — API schemas package."""

from .auth import AuthStatusResponse, Role, UserContext
from .common import (
    DependencyHealth,
    DetailedHealthResponse,
    ErrorDetail,
    ErrorResponse,
    HealthStatus,
    ResponseMetadata,
    SuccessResponse,
)
from .errors import ErrorCode, create_error_response

__all__ = [
    "AuthStatusResponse",
    "DependencyHealth",
    "DetailedHealthResponse",
    "ErrorCode",
    "ErrorDetail",
    "ErrorResponse",
    "HealthStatus",
    "ResponseMetadata",
    "Role",
    "SuccessResponse",
    "UserContext",
    "create_error_response",
]
