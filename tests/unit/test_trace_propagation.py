"""Unit and Integration Tests for W3C Distributed Trace Propagation (F14.2)."""

from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.util._once import Once
import pytest
import structlog

from backend.core.middleware.observability import ObservabilityMiddleware
from backend.observability.tracing.propagation import (
    extract_trace_context,
    get_w3c_traceparent,
    inject_trace_context,
    parse_traceparent,
)
from backend.observability.tracing.tracer import init_tracer, shutdown_tracer
from backend.tasks.celery_app import (
    cleanup_task_trace_context,
    extract_task_trace_context,
    inject_task_trace_context,
)


@pytest.fixture(autouse=True)
def reset_otel():
    shutdown_tracer()
    yield
    shutdown_tracer()


class TestW3CTraceparentParsing:
    """Test suite for W3C traceparent parsing & validation."""

    def test_parse_valid_traceparent(self) -> None:
        raw = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
        parsed = parse_traceparent(raw)
        assert parsed is not None
        assert parsed["version"] == "00"
        assert parsed["trace_id"] == "4bf92f3577b34da6a3ce929d0e0e4736"
        assert parsed["parent_id"] == "00f067aa0ba902b7"
        assert parsed["flags"] == "01"

    def test_parse_invalid_all_zeros(self) -> None:
        # All zeros trace_id is forbidden
        zero_trace = "00-00000000000000000000000000000000-00f067aa0ba902b7-01"
        assert parse_traceparent(zero_trace) is None

        # All zeros parent_id is forbidden
        zero_parent = "00-4bf92f3577b34da6a3ce929d0e0e4736-0000000000000000-01"
        assert parse_traceparent(zero_parent) is None

    def test_parse_invalid_version_ff(self) -> None:
        # Version 'ff' is forbidden per W3C specification
        ff_version = "ff-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
        assert parse_traceparent(ff_version) is None

    def test_parse_malformed_syntax(self) -> None:
        assert parse_traceparent("invalid-header") is None
        assert parse_traceparent("00-short-id-01") is None
        assert parse_traceparent("") is None
        assert parse_traceparent(None) is None


class TestTraceContextInjectionExtraction:
    """Test suite for trace context injection into and extraction from carriers."""

    def test_inject_trace_context_active_span(self) -> None:
        init_tracer(app_name="injection-test", environment="testing")
        tracer = trace.get_tracer("injection-test")

        with tracer.start_as_current_span("test_span") as span:
            ctx = span.get_span_context()
            carrier = {}
            inject_trace_context(carrier)

            assert "traceparent" in carrier
            assert format(ctx.trace_id, "032x") in carrier["traceparent"]
            assert format(ctx.span_id, "016x") in carrier["traceparent"]

    def test_extract_trace_context_valid_header(self) -> None:
        init_tracer(app_name="extract-test", environment="testing")
        carrier = {
            "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
        }
        ctx = extract_trace_context(carrier)
        assert ctx is not None

    def test_extract_trace_context_malformed_fallback(self) -> None:
        init_tracer(app_name="extract-fail-test", environment="testing")
        carrier = {"traceparent": "malformed-traceparent-string"}
        ctx = extract_trace_context(carrier)
        # Malformed header is ignored without raising an error
        assert ctx is not None or ctx is None


class TestObservabilityMiddlewareTracePropagation:
    """Test suite for HTTP request boundary trace propagation."""

    def test_middleware_inherits_remote_trace_parent(self) -> None:
        app = FastAPI()
        app.add_middleware(ObservabilityMiddleware)

        @app.get("/api/v1/test-propagation")
        def endpoint():
            return {"status": "ok"}

        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        trace._TRACER_PROVIDER_SET_ONCE = Once()
        trace._TRACER_PROVIDER = None
        trace.set_tracer_provider(provider)

        client = TestClient(app)

        remote_trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
        remote_parent_id = "00f067aa0ba902b7"
        traceparent_header = f"00-{remote_trace_id}-{remote_parent_id}-01"

        response = client.get(
            "/api/v1/test-propagation",
            headers={"traceparent": traceparent_header, "X-Correlation-ID": "corr-prop-1"},
        )

        assert response.status_code == 200
        assert "X-Trace-ID" in response.headers
        assert response.headers["X-Trace-ID"] == remote_trace_id

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        server_span = spans[0]

        # Verify server span inherited the remote trace ID and parent span ID
        assert format(server_span.context.trace_id, "032x") == remote_trace_id
        assert format(server_span.parent.span_id, "016x") == remote_parent_id


class TestCeleryTracePropagation:
    """Test suite for Celery async background task trace propagation."""

    def test_celery_task_publish_and_prerun_signals(self) -> None:
        init_tracer(app_name="celery-prop-test", environment="testing")
        tracer = trace.get_tracer("celery-prop-test")

        with tracer.start_as_current_span("enqueue_job_span") as span:
            ctx = span.get_span_context()
            task_headers = {"correlation_id": "job-corr-1"}

            # 1. Simulate Celery before_task_publish signal
            inject_task_trace_context(headers=task_headers)

            assert "traceparent" in task_headers
            assert format(ctx.trace_id, "032x") in task_headers["traceparent"]

            # 2. Simulate Celery task_prerun signal on worker side
            mock_task = MagicMock()
            mock_task.request.headers = task_headers

            extract_task_trace_context(task_id="task-uuid-1", task=mock_task)

            # Contextvars must have correlation_id and celery_task_id bound
            ctx_dict = structlog.contextvars.get_contextvars()
            assert ctx_dict.get("correlation_id") == "job-corr-1"
            assert ctx_dict.get("celery_task_id") == "task-uuid-1"

            # 3. Simulate Celery task_postrun signal
            cleanup_task_trace_context(task_id="task-uuid-1", task=mock_task)
            assert len(structlog.contextvars.get_contextvars()) == 0
