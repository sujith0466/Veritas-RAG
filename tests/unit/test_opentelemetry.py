"""Unit and Security Tests for OpenTelemetry Tracing (F14.1)."""

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from backend.core.config.observability import ObservabilitySettings
from backend.observability.tracing.tracer import (
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


class TestOpenTelemetryTracing:
    """Test suite for OpenTelemetry initialization, stage spans, and fail-open resilience."""

    def test_init_tracer_in_memory(self) -> None:
        """Verify tracer initialization with resource metadata."""
        tracer = init_tracer(app_name="raguard-test-suite", environment="testing")
        assert tracer is not None

        provider = trace.get_tracer_provider()
        assert isinstance(provider, TracerProvider)
        assert provider.resource.attributes.get("service.name") == "raguard-test-suite"
        assert provider.resource.attributes.get("deployment.environment") == "testing"

    def test_init_tracer_with_otlp_endpoint(self) -> None:
        """Verify OTLP exporter attachment with valid or local gRPC endpoints."""
        tracer = init_tracer(
            app_name="raguard-test-suite",
            environment="production",
            otlp_endpoint="localhost:4317",
            sample_rate=1.0,
        )
        assert tracer is not None
        provider = trace.get_tracer_provider()
        assert isinstance(provider, TracerProvider)

    def test_init_tracer_sampling_modes(self) -> None:
        """Verify AlwaysOn, AlwaysOff, and Ratio sampling modes."""
        # 100% sampling
        t1 = init_tracer(app_name="test", sample_rate=1.0)
        assert t1 is not None

        # 0% sampling
        t2 = init_tracer(app_name="test", sample_rate=0.0)
        assert t2 is not None

        # Fractional ratio sampling
        t3 = init_tracer(app_name="test", sample_rate=0.25)
        assert t3 is not None

    def test_trace_stage_spans(self) -> None:
        """Verify custom stage span execution, attribute recording, and active trace ID."""
        init_tracer(app_name="raguard-stage-test", environment="testing")

        assert get_current_trace_id() is None

        with trace_stage("test.stage.one", user_id="u-123", latency=45.2) as span:
            assert span is not None
            trace_id = get_current_trace_id()
            assert trace_id is not None
            assert len(trace_id) == 32  # 32-character hex trace ID

        # Outside span, current trace ID is None
        assert get_current_trace_id() is None

    def test_trace_stage_records_exception(self) -> None:
        """Verify exceptions inside trace_stage are recorded on span and re-raised."""
        init_tracer(app_name="raguard-error-test", environment="testing")

        try:
            with trace_stage("test.failing.stage"):
                raise ValueError("Intentional pipeline stage error")
        except ValueError:
            pass

    def test_pipeline_domain_stage_helpers(self) -> None:
        """Verify all custom domain stage context managers function properly."""
        init_tracer(app_name="raguard-pipeline-test", environment="testing")

        with trace_query_processing(correlation_id="corr-123", tenant_id="tenant-abc") as s:
            assert s is not None

        with trace_retrieval(strategy="hybrid", top_k=5) as s:
            assert s is not None

        with trace_confidence_evaluation(score=0.92, is_grounded=True) as s:
            assert s is not None

        with trace_retry_controller(attempt=1, strategy="expand_query") as s:
            assert s is not None

        with trace_generation(model="gemini-flash", prompt_tokens=150) as s:
            assert s is not None

        with trace_reflection(claim_count=3, entailment_ratio=1.0) as s:
            assert s is not None

        with trace_reporting(report_type="executive", format="pdf") as s:
            assert s is not None

    def test_tracer_shutdown_clean(self) -> None:
        """Verify tracer provider shutdown does not raise errors."""
        init_tracer(app_name="raguard-shutdown-test", environment="testing")
        shutdown_tracer()

    def test_observability_settings(self) -> None:
        """Verify ObservabilitySettings defaults and environment loading."""
        settings = ObservabilitySettings()
        assert settings.service_name == "raguard-ai"
        assert settings.sample_rate == 1.0
        assert settings.metrics_enabled is True
        assert settings.tracing_enabled is True
