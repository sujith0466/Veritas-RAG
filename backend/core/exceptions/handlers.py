"""FastAPI exception handlers.

Maps RAGuard custom exceptions and standard HTTP exceptions to a consistent
JSON error response envelope. All error responses follow the ErrorResponse schema
so clients have a single parsing contract regardless of error type.
"""

from collections.abc import Callable, Coroutine
from typing import Any
import uuid

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
import structlog

from .auth import AuthenticationException, AuthorizationException
from .base import InfrastructureException, RAGuardException

logger = structlog.get_logger(__name__)


def _error_response(
    request: Request,
    status_code: int,
    error_code: str,
    message: str,
    detail: dict[str, Any] | None = None,
) -> JSONResponse:
    """Build a standardised error response payload."""
    correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": {
                "code": error_code,
                "message": message,
                "detail": detail or {},
                "request_id": correlation_id,
            },
        },
        headers={"X-Correlation-ID": correlation_id},
    )


# ── Handler: RAGuard domain/infrastructure exceptions ─────────────────────────

async def raguard_exception_handler(
    request: Request, exc: RAGuardException
) -> JSONResponse:
    """Handle all custom RAGuard exceptions uniformly."""
    log = logger.bind(
        error_code=exc.error_code,
        path=request.url.path,
        method=request.method,
    )
    if isinstance(exc, InfrastructureException):
        log.error("Infrastructure exception", error=str(exc))
    elif isinstance(exc, (AuthenticationException, AuthorizationException)):
        log.warning("Auth exception", error=str(exc))
    else:
        log.info("Application exception", error=str(exc))

    return _error_response(
        request=request,
        status_code=exc.http_status,
        error_code=exc.error_code,
        message=exc.message,
        detail=exc.detail,
    )


# ── Handler: Pydantic request validation errors ────────────────────────────────

async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle Pydantic v2 validation errors from FastAPI request parsing."""
    errors = [
        {
            "field": ".".join(str(loc) for loc in err["loc"]),
            "message": err["msg"],
            "type": err["type"],
        }
        for err in exc.errors()
    ]
    logger.warning(
        "Request validation failed",
        path=request.url.path,
        error_count=len(errors),
    )
    return _error_response(
        request=request,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        error_code="VAL_002",
        message="Request body validation failed",
        detail={"errors": errors},
    )


# ── Handler: Starlette HTTP exceptions (404, 405, etc.) ───────────────────────

async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Handle standard HTTP exceptions raised by FastAPI/Starlette."""
    logger.info(
        "HTTP exception",
        status_code=exc.status_code,
        path=request.url.path,
    )
    # Map HTTP status to a semantic error code
    code_map: dict[int, str] = {
        400: "HTTP_400",
        401: "AUTH_001",
        403: "AUTH_004",
        404: "NOT_FOUND_001",
        405: "HTTP_405",
        429: "RATE_001",
        500: "INTERNAL_001",
    }
    error_code = code_map.get(exc.status_code, f"HTTP_{exc.status_code}")
    return _error_response(
        request=request,
        status_code=exc.status_code,
        error_code=error_code,
        message=exc.detail if isinstance(exc.detail, str) else str(exc.detail),
    )


# ── Handler: Unhandled exceptions ─────────────────────────────────────────────

async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Catch-all for unexpected exceptions.

    Logs the full traceback for operator visibility but returns a safe,
    non-leaking error message to the client.
    """
    correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
    logger.exception(
        "Unhandled exception",
        path=request.url.path,
        method=request.method,
        correlation_id=correlation_id,
    )
    return _error_response(
        request=request,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code="INTERNAL_000",
        message="An internal server error occurred",
        detail={"correlation_id": correlation_id},
    )


def get_exception_handlers() -> (
    list[
        tuple[
            type[Exception],
            Callable[[Request, Any], Coroutine[Any, Any, JSONResponse]],
        ]
    ]
):
    """Return the list of (exception_type, handler) pairs to register with FastAPI."""
    return [
        (RAGuardException, raguard_exception_handler),
        (RequestValidationError, validation_exception_handler),
        (StarletteHTTPException, http_exception_handler),
        (Exception, unhandled_exception_handler),
    ]
