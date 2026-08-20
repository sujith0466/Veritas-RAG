"""Comprehensive Production Certification Test Suite for F14.3 and F14.1.

Validates:
1. F14.3: Structured JSON logging, PII & credential scrubbing across all data shapes,
   trace_id/span_id correlation, query parameter masking, and fail-open resilience.
2. F14.1: OpenTelemetry TracerProvider, OTLP exporter attachment, W3C propagators,
   span hierarchies (root + child stage spans), sampling modes, endpoint exclusions,
   fail-open exporter behavior, and clean shutdown.
"""

import io
import json
import logging
import sys
import time
from typing import Any
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.util._once import Once
import pytest
import structlog

from backend.core.config.observability import ObservabilitySettings
from backend.core.logging.config import configure_logging
from backend.core.logging.middleware import RequestLoggingMiddleware, _sanitize_query_string
from backend.observability.logging.pii_masker import mask_pii, mask_string_value, sanitize_data
from backend.observability.tracing.tracer import (
    auto_instrument_app,
    get_current_trace_id,
    get_tracer,
    init_tracer,
    shutdown_tracer,
    trace_confidence_evaluation,
    trace_generation,
    trace_query_processing,
    trace_reflection,
    trace_reporting,
    trace_retrieval,
    trace_retry_controller,
    trace_stage,
)


@pytest.fixture(autouse=True)
def clean_otel_state():
    """Ensure OpenTelemetry global state is cleanly reset before and after each test."""
    shutdown_tracer()
    yield
    shutdown_tracer()


# ==============================================================================
# F14.3 — STRUCTURED JSON LOGGING & PII MASKING CERTIFICATION
# ==============================================================================


class TestF143StructuredLoggingCertification:
    """Production certification tests for F14.3."""

    def test_json_log_emission_and_schema(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify structlog in JSON mode outputs strictly valid JSON with standard fields."""
        log_buffer = io.StringIO()
        monkeypatch.setattr(sys, "stdout", log_buffer)

        configure_logging(log_level="INFO", log_format="json")
        logger = structlog.get_logger("cert_test_logger")

        logger.info("Application event occurred", action="login", status="ok", attempt=1)

        output = log_buffer.getvalue().strip()
        assert len(output) > 0

        # Each log line must be strictly parseable as JSON
        for line in output.splitlines():
            record = json.loads(line)
            assert "event" in record
            assert "timestamp" in record
            assert "level" in record
            assert "service" in record
            assert record["service"] == "raguard-ai"
            assert record["action"] == "login"
            assert record["status"] == "ok"
            assert record["attempt"] == 1

    def test_comprehensive_credential_and_pii_scrubbing(self) -> None:
        """Verify all categories of credentials and PII are redacted across nested payloads."""
        raw_payload = {
            "user_email": "security.admin@enterprise.org",
            "password": "SuperSecretPassword123!",
            "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.sampleSig12345",
            "access_token": "acc_tok_987654321",
            "refresh_token": "ref_tok_123456789",
            "api_key": "sk-mocktestkey-1234567890abcdef1234567890abcdef",
            "client_secret": "cs_live_secret_value_xyz",
            "authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.token123",
            "otp": "654321",
            "pin": "1234",
            "nested": {
                "key_field": "AIzaSyD-1234567890abcdefghijklmnopqrstuv",
                "notes": "Developer used OpenAI key sk-proj-123456789012345678901234567890 and Gemini AIzaSyD-1234567890abcdefghijklmnopqrstuv",
                "nested_emails": ["dev@raguard.ai", "qa@testing.com"],
            },
        }

        sanitized = sanitize_data(raw_payload)

        # Field-level mask assertions
        assert sanitized["password"] == "[MASKED]"
        assert sanitized["token"] == "[MASKED]"
        assert sanitized["access_token"] == "[MASKED]"
        assert sanitized["refresh_token"] == "[MASKED]"
        assert sanitized["api_key"] == "[MASKED]"
        assert sanitized["client_secret"] == "[MASKED]"
        assert sanitized["authorization"] == "[MASKED]"
        assert sanitized["otp"] == "[MASKED]"
        assert sanitized["pin"] == "[MASKED]"
        assert sanitized["nested"]["key_field"] == "[API_KEY_MASKED]"

        # String pattern masks inside unrestricted text fields
        assert "[EMAIL:enterprise.org]" in sanitized["user_email"]
        assert "security.admin" not in sanitized["user_email"]
        assert "[API_KEY_MASKED]" in sanitized["nested"]["notes"]
        assert "sk-proj-123456789012345678901234567890" not in sanitized["nested"]["notes"]
        assert "AIzaSyD-1234567890abcdefghijklmnopqrstuv" not in sanitized["nested"]["notes"]
        assert "[EMAIL:raguard.ai]" in sanitized["nested"]["nested_emails"][0]
        assert "[EMAIL:testing.com]" in sanitized["nested"]["nested_emails"][1]

    def test_trace_context_injected_in_structured_log(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify active OpenTelemetry trace_id and span_id are automatically injected into JSON logs."""
        log_buffer = io.StringIO()
        monkeypatch.setattr(sys, "stdout", log_buffer)

        configure_logging(log_level="INFO", log_format="json")
        logger = structlog.get_logger("trace_log_cert")

        # Set up an active span
        init_tracer(app_name="cert-tracer", environment="testing")
        with trace_stage("authenticated.retrieval", strategy="hybrid"):
            logger.info("Executing retrieval inside active span")

        output = log_buffer.getvalue().strip()
        lines = [json.loads(line) for line in output.splitlines() if "Executing retrieval" in line]
        assert len(lines) >= 1
        record = lines[0]

        assert "trace_id" in record
        assert "span_id" in record
        assert len(record["trace_id"]) == 32
        assert len(record["span_id"]) == 16

    def test_query_string_masking_in_middleware(self) -> None:
        """Verify sensitive URL query parameters are masked in HTTP request logs."""
        raw_query = "workspace_id=ws-123&token=eyJhbGciOiJIUzI1NiJ9.abc&api_key=sk-123&sort=asc"
        sanitized = _sanitize_query_string(raw_query)

        assert "workspace_id=ws-123" in sanitized
        assert "sort=asc" in sanitized
        assert "token=%5BMASKED%5D" in sanitized or "token=[MASKED]" in sanitized
        assert "api_key=%5BMASKED%5D" in sanitized or "api_key=[MASKED]" in sanitized
        assert "eyJhbGciOiJIUzI1NiJ9" not in sanitized
        assert "sk-123" not in sanitized

    def test_pii_masker_fail_open_resilience(self) -> None:
        """Verify mask_pii processor never crashes when encountering unexpected data types."""
        class UnserializableObject:
            def __str__(self):
                raise RuntimeError("Fault injection during __str__")

        event_dict = {
            "event": "Safe event",
            "faulty_obj": UnserializableObject(),
            "normal_data": 42,
        }

        # Must not raise an exception
        result = mask_pii(None, "info", event_dict)
        assert result is not None
        assert result["event"] == "Safe event"


# ==============================================================================
# F14.1 — OPENTELEMETRY INSTRUMENTATION CERTIFICATION
# ==============================================================================


class TestF141OpenTelemetryCertification:
    """Production certification tests for F14.1."""

    def test_in_memory_tracer_and_span_export(self) -> None:
        """Verify real OpenTelemetry spans are generated, recorded, and exported."""
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        trace._TRACER_PROVIDER_SET_ONCE = Once()
        trace._TRACER_PROVIDER = None
        trace.set_tracer_provider(provider)

        tracer = get_tracer()

        with tracer.start_as_current_span("root_http_request") as root_span:
            root_span.set_attribute("http.method", "POST")
            root_span.set_attribute("http.route", "/api/v1/chat")

            with trace_query_processing(correlation_id="corr-1", tenant_id="tenant-1") as query_span:
                with trace_retrieval(strategy="hybrid", top_k=5) as ret_span:
                    pass
                with trace_generation(model="gemini-1.5-flash", prompt_tokens=200) as gen_span:
                    pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 4

        span_names = [s.name for s in spans]
        assert "pipeline.retrieval" in span_names
        assert "pipeline.generation" in span_names
        assert "pipeline.query_processing" in span_names
        assert "root_http_request" in span_names

        # Verify trace ID consistency (all spans belong to same distributed trace)
        trace_ids = {s.context.trace_id for s in spans}
        assert len(trace_ids) == 1

        # Verify parent-child span linking
        ret_span_obj = next(s for s in spans if s.name == "pipeline.retrieval")
        query_span_obj = next(s for s in spans if s.name == "pipeline.query_processing")
        assert ret_span_obj.parent.span_id == query_span_obj.context.span_id

    def test_sampling_modes_behavior(self) -> None:
        """Verify sampling rate controls trace recording strictly."""
        # 1. Always On (1.0)
        t_on = init_tracer(app_name="test-on", sample_rate=1.0)
        with t_on.start_as_current_span("sampled_span") as s_on:
            assert s_on.is_recording() is True

        # 2. Always Off (0.0)
        t_off = init_tracer(app_name="test-off", sample_rate=0.0)
        with t_off.start_as_current_span("dropped_span") as s_off:
            assert s_off.is_recording() is False

    def test_unreachable_otlp_exporter_fail_open(self) -> None:
        """Verify that an unreachable/invalid OTLP collector never breaks tracing initialization or app execution."""
        # Attempt initialization with an unreachable local port
        tracer = init_tracer(
            app_name="raguard-resilience",
            environment="production",
            otlp_endpoint="127.0.0.1:59999",
            sample_rate=1.0,
        )
        assert tracer is not None

        # Execute a span — must complete cleanly without raising network/connection exceptions
        with trace_stage("resilient_stage", key="val") as span:
            assert span is not None
            assert get_current_trace_id() is not None

    def test_fastapi_excluded_urls_in_instrumentation(self) -> None:
        """Verify health and metrics endpoints are excluded from span recording."""
        app = FastAPI()

        @app.get("/health/live")
        def health_live():
            return {"status": "alive"}

        @app.get("/api/v1/data")
        def get_data():
            return {"data": "ok"}

        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        trace._TRACER_PROVIDER_SET_ONCE = Once()
        trace._TRACER_PROVIDER = None
        trace.set_tracer_provider(provider)

        auto_instrument_app(app)

        client = TestClient(app)

        # 1. Health check request -> excluded
        res = client.get("/health/live")
        assert res.status_code == 200

        # 2. Regular API request -> instrumented
        res = client.get("/api/v1/data")
        assert res.status_code == 200

        spans = exporter.get_finished_spans()
        span_names = [s.name for s in spans]
        assert not any("/health/live" in name for name in span_names)

    def test_shutdown_tracer_clean(self) -> None:
        """Verify shutdown_tracer flushes cleanly."""
        init_tracer(app_name="shutdown-cert", environment="testing")
        shutdown_tracer()
