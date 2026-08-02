"""Request/response logging middleware.

Logs every incoming request and its response with:
- HTTP method, path, query string
- Response status code
- Request duration in milliseconds
- Correlation ID (injected by CorrelationMiddleware first)
"""

import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp
import structlog

logger = structlog.get_logger(__name__)

# Paths that should NOT be logged (health checks create too much noise)
_SKIP_LOG_PATHS: frozenset[str] = frozenset(
    {
        "/api/v1/health/live",
        "/api/v1/health/ready",
        "/favicon.ico",
        "/metrics",
    }
)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every request/response pair with timing and correlation ID."""

    def __init__(self, app: ASGIApp, log_requests: bool = True) -> None:
        super().__init__(app)
        self._log_requests = log_requests

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if not self._log_requests or request.url.path in _SKIP_LOG_PATHS:
            return await call_next(request)

        correlation_id = getattr(request.state, "correlation_id", "unknown")
        start_time = time.perf_counter()

        # Bind correlation ID into structlog context for this request's duration
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

        logger.info(
            "Request started",
            method=request.method,
            path=request.url.path,
            query=str(request.url.query) or None,
            client=request.client.host if request.client else None,
        )

        response = await call_next(request)

        duration_ms = (time.perf_counter() - start_time) * 1000
        log = logger.bind(
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
        )

        if response.status_code >= 500:
            log.error("Request completed with server error")
        elif response.status_code >= 400:
            log.warning("Request completed with client error")
        else:
            log.info("Request completed")

        structlog.contextvars.clear_contextvars()
        return response
