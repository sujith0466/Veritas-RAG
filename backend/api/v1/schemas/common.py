"""Standard API response schemas.

All API responses — success and error — follow a consistent envelope structure.
This gives API clients a single parsing contract regardless of the endpoint.

Success: {"success": true, "data": <T>, "metadata": {...}}
Error:   {"success": false, "error": {"code": "...", "message": "...", ...}}
"""

from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ResponseMetadata(BaseModel):
    """Metadata attached to every successful response."""

    request_id: str = Field(description="Correlation ID from X-Correlation-ID header")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp when the response was generated",
    )
    version: str = Field(default="1.0.0", description="API version")


class SuccessResponse(BaseModel, Generic[T]):
    """Standard success response envelope.

    Every successful API response is wrapped in this model.

    Example:
        {
            "success": true,
            "data": {"id": "...", "name": "..."},
            "metadata": {"request_id": "...", "timestamp": "...", "version": "1.0.0"}
        }
    """

    success: bool = True
    data: T
    metadata: ResponseMetadata


class ErrorDetail(BaseModel):
    """Structured error information."""

    code: str = Field(
        description="Machine-readable error code (e.g., AUTH_001, VAL_002)"
    )
    message: str = Field(description="Human-readable error description")
    detail: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional structured context for debugging",
    )
    request_id: str = Field(description="Correlation ID for tracing this error")


class ErrorResponse(BaseModel):
    """Standard error response envelope.

    Every error response — regardless of type — follows this structure.

    Example:
        {
            "success": false,
            "error": {
                "code": "AUTH_001",
                "message": "Authentication required",
                "detail": {},
                "request_id": "uuid"
            }
        }
    """

    success: bool = False
    error: ErrorDetail


class HealthStatus(BaseModel):
    """Overall system health status."""

    status: str = Field(description="healthy | degraded | unhealthy")
    version: str
    environment: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DependencyHealth(BaseModel):
    """Health status of a single downstream dependency."""

    name: str
    status: str = Field(description="healthy | unhealthy | unknown")
    latency_ms: float | None = None
    error: str | None = None
    info: dict[str, Any] | None = None


class DetailedHealthResponse(BaseModel):
    """Full health response with per-dependency breakdown."""

    status: str
    version: str
    environment: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    dependencies: list[DependencyHealth]
