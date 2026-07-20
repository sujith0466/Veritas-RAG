"""Observability middleware for HTTP request metrics and distributed tracing.

Tracks request timing, active request gauges, status code counts, and wraps
each request in an OpenTelemetry span with correlation ID propagation.
"""

import time
from typing import Any
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp
import structlog

from backend.observability.metrics import (
    HTTP_REQUESTS_ACTIVE,
    record_error_metric,
    record_http_request,
)
from backend.observability.tracing import get_tracer

logger = structlog.get_logger(__name__)


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Middleware for automated Prometheus metrics and OpenTelemetry tracing."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        method = request.method
        # Extract normalized path to avoid metric cardinality explosion on dynamic IDs
        endpoint = request.url.path
        if hasattr(request, "route") and request.route and hasattr(request.route, "path"):
            endpoint = request.route.path

        # Ignore metrics endpoint itself from skewing latency stats if desired, or include
        if endpoint in ("/metrics", "/api/v1/metrics", "/health"):
            return await call_next(request)

        correlation_id = getattr(request.state, "correlation_id", "unknown")
        tracer = get_tracer()

        HTTP_REQUESTS_ACTIVE.labels(method=method, endpoint=endpoint).inc()
        start_time = time.perf_counter()
        status_code = 500

        try:
            if tracer is not None and hasattr(tracer, "start_as_current_span"):
                with tracer.start_as_current_span(f"{method} {endpoint}") as span:
                    span.set_attribute("http.method", method)
                    span.set_attribute("http.target", endpoint)
                    span.set_attribute("correlation_id", str(correlation_id))

                    try:
                        response = await call_next(request)
                        status_code = response.status_code
                        span.set_attribute("http.status_code", status_code)
                        return response
                    except Exception as exc:
                        status_code = 500
                        if hasattr(span, "record_exception"):
                            span.record_exception(exc)
                        record_error_metric("SYS_500", "http_middleware")
                        raise
            else:
                response = await call_next(request)
                status_code = response.status_code
                return response
        finally:
            duration = time.perf_counter() - start_time
            HTTP_REQUESTS_ACTIVE.labels(method=method, endpoint=endpoint).dec()
            record_http_request(method, endpoint, status_code, duration)
            if status_code >= 500:
                record_error_metric(f"SYS_{status_code}", "http_request")
