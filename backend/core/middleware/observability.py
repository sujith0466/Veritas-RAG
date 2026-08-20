"""Observability middleware for HTTP request metrics and distributed tracing.

Tracks request timing, active request gauges, status code counts, and wraps
each request in an OpenTelemetry span with correlation ID propagation.
"""

import time

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
from backend.observability.tracing.propagation import extract_trace_context

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
        if (
            hasattr(request, "route")
            and request.route
            and hasattr(request.route, "path")
        ):
            endpoint = request.route.path

        # Ignore metrics and health endpoints from skewing stats if desired
        if endpoint in ("/metrics", "/api/v1/metrics", "/health", "/health/live", "/health/ready", "/health/startup"):
            return await call_next(request)

        correlation_id = getattr(request.state, "correlation_id", "unknown")
        tracer = get_tracer()
        parent_ctx = extract_trace_context(dict(request.headers))

        HTTP_REQUESTS_ACTIVE.labels(method=method, endpoint=endpoint).inc()
        start_time = time.perf_counter()
        status_code = 500

        try:
            if tracer is not None and hasattr(tracer, "start_as_current_span"):
                with tracer.start_as_current_span(
                    f"{method} {endpoint}", context=parent_ctx
                ) as span:
                    span.set_attribute("http.method", method)
                    span.set_attribute("http.target", endpoint)
                    span.set_attribute("correlation_id", str(correlation_id))

                    ctx = span.get_span_context() if hasattr(span, "get_span_context") else None
                    trace_id_hex = format(ctx.trace_id, "032x") if ctx and ctx.trace_id else None

                    try:
                        response = await call_next(request)
                        status_code = response.status_code
                        span.set_attribute("http.status_code", status_code)
                        if trace_id_hex:
                            response.headers["X-Trace-ID"] = trace_id_hex
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
