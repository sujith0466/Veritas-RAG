"""Prometheus metrics registry and production instrumentation definitions.

Exposes exact counters, histograms, and gauges for HTTP requests, AI pipeline
stages, self-correction interventions, confidence scores, and reliability distributions.
"""

from typing import Any
import structlog

try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        REGISTRY,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"
    REGISTRY = None

    class _MockMetric:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass
        def labels(self, *args: Any, **kwargs: Any) -> "_MockMetric":
            return self
        def inc(self, amount: float = 1.0) -> None:
            pass
        def dec(self, amount: float = 1.0) -> None:
            pass
        def set(self, value: float) -> None:
            pass
        def observe(self, amount: float) -> None:
            pass

    Counter = _MockMetric  # type: ignore
    Gauge = _MockMetric  # type: ignore
    Histogram = _MockMetric  # type: ignore

    def generate_latest(registry: Any = None) -> bytes:
        return b"# Prometheus metrics disabled (prometheus_client not installed)\n"

logger = structlog.get_logger(__name__)

# ── 1. HTTP Request Metrics ───────────────────────────────────────────────────

HTTP_REQUESTS_TOTAL = Counter(
    "raguard_http_requests_total",
    "Total HTTP requests handled across all API endpoints.",
    ["method", "endpoint", "status_code"],
)

HTTP_REQUESTS_ACTIVE = Gauge(
    "raguard_http_requests_active",
    "Currently active HTTP requests being processed.",
    ["method", "endpoint"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "raguard_http_request_duration_seconds",
    "HTTP request latency distribution in seconds.",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# ── 2. Query & Pipeline Metrics ───────────────────────────────────────────────

QUERIES_PROCESSED_TOTAL = Counter(
    "raguard_queries_processed_total",
    "Total AI queries executed through the pipeline.",
    ["tenant_id", "outcome"],
)

PIPELINE_STAGE_DURATION_SECONDS = Histogram(
    "raguard_pipeline_stage_duration_seconds",
    "Duration of individual pipeline stages in seconds.",
    ["stage"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 3.0],
)

ERRORS_TOTAL = Counter(
    "raguard_errors_total",
    "Total domain and system errors triggered across all modules.",
    ["error_code", "stage"],
)

# ── 3. AI Reliability, Self-Correction & Reflection Metrics ───────────────────

SELF_CORRECTION_RETRIES_TOTAL = Counter(
    "raguard_self_correction_retries_total",
    "Total self-correction interventions and query rewrite loops triggered.",
    ["strategy", "trigger_reason"],
)

PRE_GEN_CONFIDENCE_SCORE = Histogram(
    "raguard_pre_gen_confidence_score",
    "Distribution of pre-generation grounding confidence scores (0.0 - 1.0).",
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 1.0],
)

POST_GEN_RELIABILITY_SCORE = Histogram(
    "raguard_post_gen_reliability_score",
    "Distribution of final explainable reliability scores (0.0 - 1.0).",
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 1.0],
)

REFLECTION_FAILURES_TOTAL = Counter(
    "raguard_reflection_failures_total",
    "Total post-generation claim entailment failures detected.",
    ["reason"],
)

HALLUCINATION_DETECTIONS_TOTAL = Counter(
    "raguard_hallucination_detections_total",
    "Total ungrounded or conflicting hallucination instances intercepted.",
    ["severity"],
)


# ── Helper Recording Functions ────────────────────────────────────────────────

def record_http_request(method: str, endpoint: str, status_code: int, duration_seconds: float) -> None:
    """Record a completed HTTP request metrics."""
    status_str = str(status_code)
    HTTP_REQUESTS_TOTAL.labels(method=method, endpoint=endpoint, status_code=status_str).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(method=method, endpoint=endpoint).observe(duration_seconds)


def record_query_metric(tenant_id: str, outcome: str, duration_seconds: float) -> None:
    """Record an AI query execution metric and total pipeline duration."""
    QUERIES_PROCESSED_TOTAL.labels(tenant_id=tenant_id, outcome=outcome).inc()
    PIPELINE_STAGE_DURATION_SECONDS.labels(stage="total_pipeline").observe(duration_seconds)


def record_stage_duration(stage: str, duration_seconds: float) -> None:
    """Record latency observation for a specific pipeline stage."""
    PIPELINE_STAGE_DURATION_SECONDS.labels(stage=stage).observe(duration_seconds)


def record_error_metric(error_code: str, stage: str) -> None:
    """Increment the error counter for a given taxonomy code and stage."""
    ERRORS_TOTAL.labels(error_code=error_code, stage=stage).inc()


def record_retry_metric(strategy: str, trigger_reason: str) -> None:
    """Record a self-correction retry trigger."""
    SELF_CORRECTION_RETRIES_TOTAL.labels(strategy=strategy, trigger_reason=trigger_reason).inc()


def record_confidence_metric(score: float) -> None:
    """Observe a pre-generation confidence score."""
    PRE_GEN_CONFIDENCE_SCORE.observe(max(0.0, min(1.0, score)))


def record_reliability_metric(score: float) -> None:
    """Observe a post-generation reliability score."""
    POST_GEN_RELIABILITY_SCORE.observe(max(0.0, min(1.0, score)))


def record_reflection_metric(failed: bool, hallucination_detected: bool, reason: str = "unsupported_claim") -> None:
    """Record reflection entailment outcomes and hallucination detections."""
    if failed:
        REFLECTION_FAILURES_TOTAL.labels(reason=reason).inc()
    if hallucination_detected:
        HALLUCINATION_DETECTIONS_TOTAL.labels(severity="high").inc()


def get_metrics_output() -> bytes:
    """Return the raw Prometheus text-format metrics buffer."""
    return generate_latest(REGISTRY)


def get_metrics_content_type() -> str:
    """Return the standard Prometheus MIME content type."""
    return str(CONTENT_TYPE_LATEST)
