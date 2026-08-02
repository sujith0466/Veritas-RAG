"""Observability Facade.

Centralizes access to Logging, Metrics, Tracing, and Correlation contexts.
Guarantees a single correlation ID propagates across all pillars.
"""

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

import structlog

from backend.observability.metrics import prometheus
from backend.observability.tracing import tracer


class ObservabilityFacade:
    """Centralized facade for enterprise observability."""

    _instance = None

    @classmethod
    def get_instance(cls) -> "ObservabilityFacade":
        """Get the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_logger(self, name: str) -> Any:
        """Return a context-aware structured logger.

        The logger will automatically inherit the correlation ID if injected
        via the CorrelationIDMiddleware or if a trace is active.
        """
        return structlog.get_logger(name)

    def get_correlation_id(self) -> str | None:
        """Retrieve the active correlation ID.

        Prioritizes the OpenTelemetry trace ID, falling back to the
        X-Correlation-ID stored in context variables by the middleware.
        """
        # First check active OTel trace
        trace_id = tracer.get_current_trace_id()
        if trace_id:
            return trace_id

        # Fallback to structlog contextvars if available
        context = structlog.contextvars.get_contextvars()
        return context.get("correlation_id")

    @contextmanager
    def trace_block(self, name: str, **attributes: Any) -> Generator[Any, None, None]:
        """Trace a logical block of execution, linking it to the active trace context."""
        correlation_id = self.get_correlation_id()
        if correlation_id and "correlation_id" not in attributes:
            attributes["correlation_id"] = correlation_id

        with tracer.trace_stage(name, **attributes) as span:
            yield span

    # ── Metric Recording ───────────────────────────────────────────────────────

    def record_stage_duration(self, stage: str, duration_seconds: float) -> None:
        """Record the duration of a specific logical stage."""
        prometheus.record_stage_duration(stage, duration_seconds)

    def record_error(self, error_code: str, stage: str) -> None:
        """Record a domain or infrastructure error occurrence."""
        prometheus.record_error_metric(error_code, stage)

    def record_http_request(
        self, method: str, endpoint: str, status_code: int, duration_seconds: float
    ) -> None:
        """Record an HTTP request outcome."""
        prometheus.record_http_request(method, endpoint, status_code, duration_seconds)


# Export singleton access helper
observability = ObservabilityFacade.get_instance()
