"""Request/response logging middleware.

Logs every incoming request and its response with:
- HTTP method, path, query string
- Response status code
- Request duration in milliseconds
- Correlation ID (injected by CorrelationMiddleware first)
"""

import time
import urllib.parse

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
        "/health/live",
        "/health/ready",
        "/health/startup",
        "/api/v1/health/startup",
        "/favicon.ico",
        "/metrics",
        "/api/v1/metrics",
    }
)

_SENSITIVE_QUERY_PARAMS: frozenset[str] = frozenset(
    {
        "token",
        "access_token",
        "refresh_token",
        "api_key",
        "apikey",
        "key",
        "secret",
        "password",
        "code",
        "auth",
        "authorization",
        "state",
        "session",
        "signature",
    }
)


def _sanitize_query_string(raw_query: str) -> str | None:
    """Mask sensitive query parameters to prevent credential leaks in access logs."""
    if not raw_query:
        return None
    try:
        parsed_params = urllib.parse.parse_qsl(raw_query, keep_blank_values=True)
        sanitized: list[tuple[str, str]] = []
        for param_key, param_val in parsed_params:
            if param_key.lower() in _SENSITIVE_QUERY_PARAMS:
                sanitized.append((param_key, "[MASKED]"))
            else:
                sanitized.append((param_key, param_val))
        return urllib.parse.urlencode(sanitized)
    except Exception:
        return "[INVALID_QUERY_MASKED]"


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

        # Bind context variables for this request's duration
        structlog.contextvars.clear_contextvars()
        ctx_vars: dict[str, str] = {"correlation_id": correlation_id}

        user_ctx = getattr(request.state, "user_context", None)
        if user_ctx:
            if hasattr(user_ctx, "workspace_id") and user_ctx.workspace_id:
                ctx_vars["workspace_id"] = str(user_ctx.workspace_id)
            if hasattr(user_ctx, "id") and user_ctx.id:
                ctx_vars["user_id"] = str(user_ctx.id)

        structlog.contextvars.bind_contextvars(**ctx_vars)

        sanitized_query = _sanitize_query_string(str(request.url.query)) if request.url.query else None

        logger.info(
            "Request started",
            method=request.method,
            path=request.url.path,
            query=sanitized_query,
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
