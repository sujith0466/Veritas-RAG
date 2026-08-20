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
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.propagate import set_global_textmap
    from opentelemetry.propagators.composite import CompositePropagator
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.sdk.trace.sampling import (
        ALWAYS_OFF,
        ALWAYS_ON,
        ParentBased,
        TraceIdRatioBased,
    )
    from opentelemetry.trace import Span, Status, StatusCode
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    trace = None
    Span = Any
    Status = Any
    StatusCode = Any

logger = structlog.get_logger(__name__)

_tracer: Any = None


def init_tracer(
    app_name: str = "raguard-ai",
    environment: str = "development",
    otlp_endpoint: str | None = None,
    sample_rate: float = 1.0,
) -> Any:
    """Initialize OpenTelemetry tracer provider with resource metadata, exporters, and propagators.

    Fail-open design: if any step fails (unreachable collector, invalid config), tracing runs
    safely in no-op mode without breaking application startup or request flows.
    """
    global _tracer  # noqa: PLW0603
    if not OTEL_AVAILABLE:
        logger.warning("OpenTelemetry SDK not installed; tracing running in no-op mode.")
        return None

    try:
        # 1. Resource Attributes
        resource = Resource.create(
            {
                "service.name": app_name,
                "deployment.environment": environment,
            }
        )

        # 2. Trace Sampling
        if sample_rate >= 1.0:
            sampler = ALWAYS_ON
        elif sample_rate <= 0.0:
            sampler = ALWAYS_OFF
        else:
            sampler = ParentBased(TraceIdRatioBased(sample_rate))

        provider = TracerProvider(resource=resource, sampler=sampler)

        # 3. Span Exporter (OTLP gRPC)
        if otlp_endpoint and otlp_endpoint.strip():
            try:
                exporter = OTLPSpanExporter(endpoint=otlp_endpoint.strip(), insecure=True)
                processor = BatchSpanProcessor(
                    exporter,
                    max_queue_size=2048,
                    max_export_batch_size=512,
                    schedule_delay_millis=5000,
                )
                provider.add_span_processor(processor)
                logger.info("OTLP span exporter attached", endpoint=otlp_endpoint)
            except Exception as exp_err:
                logger.warning(
                    "Failed to attach OTLP span exporter; continuing in-memory",
                    error=str(exp_err),
                    endpoint=otlp_endpoint,
                )

        # 4. Set Global TracerProvider
        try:
            from opentelemetry.util._once import Once

            trace._TRACER_PROVIDER_SET_ONCE = Once()
        except Exception:
            pass
        trace._TRACER_PROVIDER = None
        trace.set_tracer_provider(provider)
        _tracer = provider.get_tracer(app_name)

        # 5. Configure Global TextMap Propagators (W3C tracecontext)
        try:
            set_global_textmap(CompositePropagator([TraceContextTextMapPropagator()]))
        except Exception as prop_err:
            logger.warning("Failed to configure composite propagator", error=str(prop_err))

        logger.info(
            "OpenTelemetry tracer initialized successfully",
            app_name=app_name,
            environment=environment,
            sample_rate=sample_rate,
            otlp_enabled=bool(otlp_endpoint),
        )
        return _tracer
    except Exception as exc:
        logger.error("Failed to initialize OpenTelemetry TracerProvider", error=str(exc))
        return None


def shutdown_tracer() -> None:
    """Flush and cleanly shut down the TracerProvider on application shutdown."""
    global _tracer
    if not OTEL_AVAILABLE or trace is None:
        return
    try:
        provider = trace.get_tracer_provider()
        if hasattr(provider, "shutdown"):
            provider.shutdown()
            logger.info("OpenTelemetry tracer provider shutdown complete.")
        try:
            from opentelemetry.util._once import Once

            trace._TRACER_PROVIDER_SET_ONCE = Once()
        except Exception:
            pass
        trace._TRACER_PROVIDER = None
        _tracer = None
    except Exception as exc:
        logger.warning("Error during OpenTelemetry tracer provider shutdown", error=str(exc))


def get_tracer() -> Any:
    """Return the global OpenTelemetry tracer instance from the active provider."""
    if not OTEL_AVAILABLE or trace is None:
        return None
    provider = trace.get_tracer_provider()
    return provider.get_tracer("raguard-ai")


def auto_instrument_app(app: Any) -> None:
    """Safely apply FastAPI auto-instrumentation without crashing on error."""
    if not OTEL_AVAILABLE:
        return
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(
            app,
            excluded_urls="/health/live,/health/ready,/health/startup,/api/v1/health/*,/metrics,/api/v1/metrics,/favicon.ico",
        )
        logger.info("FastAPI OpenTelemetry auto-instrumentation active.")
    except Exception as exc:
        logger.warning("FastAPI OpenTelemetry auto-instrumentation skipped", error=str(exc))


def auto_instrument_clients() -> None:
    """Safely apply HTTPX, Redis, SQLAlchemy auto-instrumentation for outgoing client calls."""
    if not OTEL_AVAILABLE:
        return

    # HTTPX
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()
    except Exception as exc:
        logger.debug("HTTPX auto-instrumentation skipped", error=str(exc))

    # Redis
    try:
        from opentelemetry.instrumentation.redis import RedisInstrumentor

        RedisInstrumentor().instrument()
    except Exception as exc:
        logger.debug("Redis auto-instrumentation skipped", error=str(exc))

    # Celery
    try:
        from opentelemetry.instrumentation.celery import CeleryInstrumentor

        CeleryInstrumentor().instrument()
    except Exception as exc:
        logger.debug("Celery auto-instrumentation skipped", error=str(exc))


def get_tracer() -> Any:
    """Return the global OpenTelemetry tracer instance."""
    global _tracer  # noqa: PLW0603
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
                span.set_attribute(
                    k, str(v) if not isinstance(v, (int, float, bool, str)) else v
                )
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
def trace_query_processing(
    correlation_id: str, tenant_id: str, **kwargs: Any
) -> Generator[Any, None, None]:
    """Create a span for the main Query Processing pipeline entry point."""
    with trace_stage(
        "pipeline.query_processing",
        correlation_id=correlation_id,
        tenant_id=tenant_id,
        **kwargs,
    ) as span:
        yield span


@contextmanager
def trace_retrieval(
    strategy: str, top_k: int, **kwargs: Any
) -> Generator[Any, None, None]:
    """Create a span for Hybrid Retrieval & Reranking execution."""
    with trace_stage(
        "pipeline.retrieval", strategy=strategy, top_k=top_k, **kwargs
    ) as span:
        yield span


@contextmanager
def trace_confidence_evaluation(
    score: float, is_grounded: bool, **kwargs: Any
) -> Generator[Any, None, None]:
    """Create a span for Pre-Generation Confidence Evaluation."""
    with trace_stage(
        "pipeline.confidence_evaluation", score=score, is_grounded=is_grounded, **kwargs
    ) as span:
        yield span


@contextmanager
def trace_retry_controller(
    attempt: int, strategy: str, **kwargs: Any
) -> Generator[Any, None, None]:
    """Create a span for Self-Correction & Retry loop execution."""
    with trace_stage(
        "pipeline.retry_controller", attempt=attempt, strategy=strategy, **kwargs
    ) as span:
        yield span


@contextmanager
def trace_generation(
    model: str, prompt_tokens: int, **kwargs: Any
) -> Generator[Any, None, None]:
    """Create a span for Grounded Answer Generation (`LLM` call)."""
    with trace_stage(
        "pipeline.generation", model=model, prompt_tokens=prompt_tokens, **kwargs
    ) as span:
        yield span


@contextmanager
def trace_reflection(
    claim_count: int, entailment_ratio: float, **kwargs: Any
) -> Generator[Any, None, None]:
    """Create a span for Post-Generation Reflection & Claim Entailment verification."""
    with trace_stage(
        "pipeline.reflection",
        claim_count=claim_count,
        entailment_ratio=entailment_ratio,
        **kwargs,
    ) as span:
        yield span


@contextmanager
def trace_reporting(
    report_type: str, format: str, **kwargs: Any  # noqa: A002
) -> Generator[Any, None, None]:
    """Create a span for Enterprise ReportLab PDF/JSON Report Export."""
    with trace_stage(
        "pipeline.reporting", report_type=report_type, format=format, **kwargs
    ) as span:
        yield span
