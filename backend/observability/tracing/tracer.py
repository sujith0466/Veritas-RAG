"""OpenTelemetry distributed tracing setup and custom stage span helpers.

Provides clean abstractions for initializing OpenTelemetry and creating custom
spans across all major RAGuard AI pipeline stages.
"""

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any
import structlog

try:
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.trace import Span, Status, StatusCode
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    trace = None
    Span = Any
    Status = Any
    StatusCode = Any

logger = structlog.get_logger(__name__)

_tracer: Any = None


def init_tracer(app_name: str = "raguard-ai", environment: str = "development") -> Any:
    """Initialize OpenTelemetry tracer provider with resource metadata."""
    global _tracer
    if not OTEL_AVAILABLE:
        logger.warning("OpenTelemetry not installed; tracing will run in no-op mode.")
        return None

    resource = Resource.create({
        "service.name": app_name,
        "deployment.environment": environment,
    })
    provider = TracerProvider(resource=resource)
    
    # In development or when no OLTP collector is configured, we attach Console/Memory processor
    # or leave clean so tests run without network blocking
    if environment == "development":
        # Can add ConsoleSpanExporter if verbose tracing desired, or keep light for unit tests
        pass

    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer(app_name)
    logger.info("OpenTelemetry tracer initialized", app_name=app_name, environment=environment)
    return _tracer


def get_tracer() -> Any:
    """Return the global OpenTelemetry tracer instance."""
    global _tracer
    if _tracer is None and OTEL_AVAILABLE and trace is not None:
        _tracer = trace.get_tracer("raguard-ai")
    return _tracer


def get_current_trace_id() -> str | None:
    """Return the current trace ID in hex format if an active span exists."""
    if not OTEL_AVAILABLE or trace is None:
        return None
    span = trace.get_current_span()
    if span is None or not span.is_recording():
        return None
    ctx = span.get_span_context()
    if ctx and ctx.trace_id:
        return format(ctx.trace_id, "032x")
    return None


@contextmanager
def trace_stage(stage_name: str, **attributes: Any) -> Generator[Any, None, None]:
    """Context manager to trace a pipeline stage or block of execution.

    Args:
        stage_name: Name of the span (e.g., 'retrieval.dense_search').
        attributes: Key-value metadata to attach to the span.
    """
    tracer = get_tracer()
    if tracer is None:
        yield None
        return

    with tracer.start_as_current_span(stage_name) as span:
        for k, v in attributes.items():
            if v is not None:
                span.set_attribute(k, str(v) if not isinstance(v, (int, float, bool, str)) else v)
        try:
            yield span
        except Exception as exc:
            if hasattr(span, "record_exception"):
                span.record_exception(exc)
            if hasattr(span, "set_status") and StatusCode is not Any:
                span.set_status(Status(StatusCode.ERROR, str(exc)))
            raise


# ── Pipeline Stage Custom Helpers ──────────────────────────────────────────────

@contextmanager
def trace_query_processing(correlation_id: str, tenant_id: str, **kwargs: Any) -> Generator[Any, None, None]:
    """Create a span for the main Query Processing pipeline entry point."""
    with trace_stage("pipeline.query_processing", correlation_id=correlation_id, tenant_id=tenant_id, **kwargs) as span:
        yield span


@contextmanager
def trace_retrieval(strategy: str, top_k: int, **kwargs: Any) -> Generator[Any, None, None]:
    """Create a span for Hybrid Retrieval & Reranking execution."""
    with trace_stage("pipeline.retrieval", strategy=strategy, top_k=top_k, **kwargs) as span:
        yield span


@contextmanager
def trace_confidence_evaluation(score: float, is_grounded: bool, **kwargs: Any) -> Generator[Any, None, None]:
    """Create a span for Pre-Generation Confidence Evaluation."""
    with trace_stage("pipeline.confidence_evaluation", score=score, is_grounded=is_grounded, **kwargs) as span:
        yield span


@contextmanager
def trace_retry_controller(attempt: int, strategy: str, **kwargs: Any) -> Generator[Any, None, None]:
    """Create a span for Self-Correction & Retry loop execution."""
    with trace_stage("pipeline.retry_controller", attempt=attempt, strategy=strategy, **kwargs) as span:
        yield span


@contextmanager
def trace_generation(model: str, prompt_tokens: int, **kwargs: Any) -> Generator[Any, None, None]:
    """Create a span for Grounded Answer Generation (`LLM` call)."""
    with trace_stage("pipeline.generation", model=model, prompt_tokens=prompt_tokens, **kwargs) as span:
        yield span


@contextmanager
def trace_reflection(claim_count: int, entailment_ratio: float, **kwargs: Any) -> Generator[Any, None, None]:
    """Create a span for Post-Generation Reflection & Claim Entailment verification."""
    with trace_stage("pipeline.reflection", claim_count=claim_count, entailment_ratio=entailment_ratio, **kwargs) as span:
        yield span


@contextmanager
def trace_reporting(report_type: str, format: str, **kwargs: Any) -> Generator[Any, None, None]:
    """Create a span for Enterprise ReportLab PDF/JSON Report Export."""
    with trace_stage("pipeline.reporting", report_type=report_type, format=format, **kwargs) as span:
        yield span
