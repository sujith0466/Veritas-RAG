"""Standardized error code taxonomy and response models.

Defines the system-wide error codes and factory helpers for creating
consistent ErrorResponse objects across all endpoints and exception handlers.
"""

from enum import StrEnum
from typing import Any

from .common import ErrorDetail, ErrorResponse


class ErrorCode(StrEnum):
    """System-wide error code taxonomy."""

    # ── Authentication & Authorization (AUTH_xxx / PERMISSION_xxx) ───────────
    AUTH_001 = "AUTH_001"  # Missing authorization credentials
    AUTH_002 = "AUTH_002"  # Malformed, corrupted, or invalid token signature
    AUTH_003 = "AUTH_003"  # Expired authentication token
    AUTH_004 = "AUTH_004"  # General authorization failure (Forbidden)
    AUTH_005 = "AUTH_005"  # Insufficient role for operation
    PERMISSION_001 = "PERMISSION_001"  # Insufficient role/permission for operation
    PERMISSION_002 = "PERMISSION_002"  # Action denied by permission guard

    # ── Input Validation (VAL_xxx) ───────────────────────────────────────────
    VAL_001 = "VAL_001"  # General validation failure
    VAL_002 = "VAL_002"  # Pydantic schema validation failure

    # ── Resource & Infrastructure (NOT_FOUND_xxx / DB_xxx / INTERNAL_xxx) ────
    NOT_FOUND_001 = "NOT_FOUND_001"  # Resource not found
    DB_001 = "DB_001"  # Database connection or query error
    INTERNAL_001 = "INTERNAL_001"  # Unhandled server error


def create_error_response(
    code: ErrorCode | str,
    message: str,
    request_id: str,
    detail: dict[str, Any] | None = None,
) -> ErrorResponse:
    """Create a standardized ErrorResponse object.

    Args:
        code: Machine-readable error code (ErrorCode enum or string).
        message: Human-readable description of the error.
        request_id: Correlation ID for tracing.
        detail: Optional structured context dictionary.

    Returns:
        An ErrorResponse object ready for JSON serialization.
    """
    code_str = code.value if isinstance(code, ErrorCode) else str(code)
    return ErrorResponse(
        success=False,
        error=ErrorDetail(
            code=code_str,
            message=message,
            detail=detail or {},
            request_id=request_id,
        ),
    )
