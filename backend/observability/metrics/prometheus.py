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

        def labels(self, *args: Any, **kwargs: Any) -> "_MockMetric":  # noqa: ARG002
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


# ── 4. SSE Streaming Resilience Metrics (Epic 8) ──────────────────────────────

SSE_ACTIVE_STREAMS = Gauge(
    "raguard_sse_active_streams",
    "Currently active SSE streams.",
)

SSE_REPLAYED_CHUNKS_TOTAL = Counter(
    "raguard_sse_replayed_chunks_total",
    "Total number of SSE chunks replayed from Redis buffer.",
)

SSE_REDIS_BUFFER_HITS_TOTAL = Counter(
    "raguard_sse_redis_buffer_hits_total",
    "Total successful stream resumptions via Redis buffer.",
)

SSE_REDIS_BUFFER_MISSES_TOTAL = Counter(
    "raguard_sse_redis_buffer_misses_total",
    "Total stream resumptions failed due to expired/missing Redis buffer.",
)

SSE_STREAM_DURATION_SECONDS = Histogram(
    "raguard_sse_stream_duration_seconds",
    "Total duration of an SSE stream in seconds.",
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0],
)

SSE_CHUNKS_PER_STREAM = Histogram(
    "raguard_sse_chunks_per_stream",
    "Number of chunks yielded per SSE stream.",
    buckets=[10, 50, 100, 250, 500, 1000],
)

SSE_TTFT_SECONDS = Histogram(
    "raguard_sse_ttft_seconds",
    "Time to first token (TTFT) in seconds.",
    buckets=[0.5, 1.0, 2.5, 5.0, 10.0, 15.0],
)

SSE_CANCELLATIONS_TOTAL = Counter(
    "raguard_sse_cancellations_total",
    "Total number of client-initiated stream cancellations.",
)

SSE_RECONNECTS_TOTAL = Counter(
    "raguard_sse_reconnects_total",
    "Total number of stream reconnect attempts (Last-Event-ID provided).",
)

SSE_TIMEOUTS_TOTAL = Counter(
    "raguard_sse_timeouts_total",
    "Total number of timeout events during streaming.",
    ["timeout_type"],
)


# ── 5. AI Policy & Streaming Extraction Metrics (Epic 8 Batch 3) ────────────────

SSE_RELIABILITY_UPDATES_TOTAL = Counter(
    "raguard_sse_reliability_updates_total",
    "Total number of incremental reliability score updates emitted via SSE.",
)

SSE_CITATIONS_EMITTED_TOTAL = Counter(
    "raguard_sse_citations_emitted_total",
    "Total number of citation events streamed progressively via SSE.",
)

POLICY_VIOLATIONS_TOTAL = Counter(
    "raguard_policy_violations_total",
    "Total number of AI policy violations intercepted.",
    ["violation_type"],
)

PII_REDACTIONS_TOTAL = Counter(
    "raguard_pii_redactions_total",
    "Total number of PII instances redacted from prompts before LLM ingress.",
)

BLOCKED_PROMPT_TOTAL = Counter(
    "raguard_blocked_prompt_total",
    "Total number of prompts blocked due to restricted topics.",
    ["topic"],
)

PROMPT_INJECTION_DETECTED_TOTAL = Counter(
    "raguard_prompt_injection_detected_total",
    "Total number of prompt injection or jailbreak attempts detected.",
)


# ── Helper Recording Functions ────────────────────────────────────────────────


def record_http_request(
    method: str, endpoint: str, status_code: int, duration_seconds: float
) -> None:
    """Record a completed HTTP request metrics."""
    status_str = str(status_code)
    HTTP_REQUESTS_TOTAL.labels(
        method=method, endpoint=endpoint, status_code=status_str
    ).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(method=method, endpoint=endpoint).observe(
        duration_seconds
    )


def record_query_metric(tenant_id: str, outcome: str, duration_seconds: float) -> None:
    """Record an AI query execution metric and total pipeline duration."""
    QUERIES_PROCESSED_TOTAL.labels(tenant_id=tenant_id, outcome=outcome).inc()
    PIPELINE_STAGE_DURATION_SECONDS.labels(stage="total_pipeline").observe(
        duration_seconds
    )


def record_stage_duration(stage: str, duration_seconds: float) -> None:
    """Record latency observation for a specific pipeline stage."""
    PIPELINE_STAGE_DURATION_SECONDS.labels(stage=stage).observe(duration_seconds)


def record_error_metric(error_code: str, stage: str) -> None:
    """Increment the error counter for a given taxonomy code and stage."""
    ERRORS_TOTAL.labels(error_code=error_code, stage=stage).inc()


def record_retry_metric(strategy: str, trigger_reason: str) -> None:
    """Record a self-correction retry trigger."""
    SELF_CORRECTION_RETRIES_TOTAL.labels(
        strategy=strategy, trigger_reason=trigger_reason
    ).inc()


def record_confidence_metric(score: float) -> None:
    """Observe a pre-generation confidence score."""
    PRE_GEN_CONFIDENCE_SCORE.observe(max(0.0, min(1.0, score)))


def record_reliability_metric(score: float) -> None:
    """Observe a post-generation reliability score."""
    POST_GEN_RELIABILITY_SCORE.observe(max(0.0, min(1.0, score)))


def record_reflection_metric(
    failed: bool, hallucination_detected: bool, reason: str = "unsupported_claim"
) -> None:
    """Record reflection entailment outcomes and hallucination detections."""
    if failed:
        REFLECTION_FAILURES_TOTAL.labels(reason=reason).inc()
    if hallucination_detected:
        HALLUCINATION_DETECTIONS_TOTAL.labels(severity="high").inc()


def record_sse_reliability_update() -> None:
    SSE_RELIABILITY_UPDATES_TOTAL.inc()


def record_sse_citation_emitted() -> None:
    SSE_CITATIONS_EMITTED_TOTAL.inc()


def record_policy_violation(violation_type: str) -> None:
    POLICY_VIOLATIONS_TOTAL.labels(violation_type=violation_type).inc()


def record_pii_redaction() -> None:
    PII_REDACTIONS_TOTAL.inc()


def record_blocked_prompt(topic: str) -> None:
    BLOCKED_PROMPT_TOTAL.labels(topic=topic).inc()


def record_prompt_injection() -> None:
    PROMPT_INJECTION_DETECTED_TOTAL.inc()


# ── 8. Workspace Lifecycle & Retention Metrics ───────────────────────────────

WORKSPACES_SOFT_DELETED_TOTAL = Counter(
    "raguard_workspaces_soft_deleted_total",
    "Total workspaces soft deleted.",
)

WORKSPACES_RESTORED_TOTAL = Counter(
    "raguard_workspaces_restored_total",
    "Total workspaces restored from soft deletion.",
)

WORKSPACES_HARD_DELETED_TOTAL = Counter(
    "raguard_workspaces_hard_deleted_total",
    "Total workspaces permanently hard deleted.",
)

WORKSPACE_CLEANUP_FAILURES_TOTAL = Counter(
    "raguard_workspace_cleanup_failures_total",
    "Total cleanup failure incidents encountered during workspace purge.",
    ["stage"],
)

WORKSPACE_RETENTION_WORKER_DURATION_SECONDS = Histogram(
    "raguard_workspace_retention_worker_duration_seconds",
    "Time taken in seconds to run workspace retention cleanup batch.",
)


def record_workspace_soft_deleted() -> None:
    WORKSPACES_SOFT_DELETED_TOTAL.inc()


def record_workspace_restored() -> None:
    WORKSPACES_RESTORED_TOTAL.inc()


def record_workspace_hard_deleted() -> None:
    WORKSPACES_HARD_DELETED_TOTAL.inc()


def record_workspace_cleanup_failure(stage: str) -> None:
    WORKSPACE_CLEANUP_FAILURES_TOTAL.labels(stage=stage).inc()


def record_retention_worker_duration(duration_seconds: float) -> None:
    WORKSPACE_RETENTION_WORKER_DURATION_SECONDS.observe(duration_seconds)


# ── 9. Feature Flag Metrics ──────────────────────────────────────────────────

FEATURE_FLAG_EVALUATIONS_TOTAL = Counter(
    "raguard_feature_flag_evaluations_total",
    "Total feature flag evaluations executed.",
    ["flag_key", "result", "reason"],
)

FEATURE_FLAG_CACHE_HITS_TOTAL = Counter(
    "raguard_feature_flag_cache_hits_total",
    "Total feature flag cache hits by tier.",
    ["tier"],
)

FEATURE_FLAG_CACHE_MISSES_TOTAL = Counter(
    "raguard_feature_flag_cache_misses_total",
    "Total feature flag cache misses by tier.",
    ["tier"],
)

FEATURE_FLAG_EVALUATION_DURATION_SECONDS = Histogram(
    "raguard_feature_flag_evaluation_duration_seconds",
    "Time taken to evaluate a feature flag in seconds.",
    ["tier"],
)

FEATURE_FLAG_KILLSWITCHES_ACTIVE = Gauge(
    "raguard_feature_flag_killswitches_active",
    "Current count of active emergency killswitches.",
)


def record_feature_flag_evaluation(flag_key: str, result: str, reason: str) -> None:
    FEATURE_FLAG_EVALUATIONS_TOTAL.labels(
        flag_key=flag_key, result=result, reason=reason
    ).inc()


def record_feature_flag_cache_hit(tier: str) -> None:
    FEATURE_FLAG_CACHE_HITS_TOTAL.labels(tier=tier).inc()


def record_feature_flag_cache_miss(tier: str) -> None:
    FEATURE_FLAG_CACHE_MISSES_TOTAL.labels(tier=tier).inc()


def record_feature_flag_duration(tier: str, duration_seconds: float) -> None:
    FEATURE_FLAG_EVALUATION_DURATION_SECONDS.labels(tier=tier).observe(duration_seconds)


def set_active_killswitches_count(count: int) -> None:
    FEATURE_FLAG_KILLSWITCHES_ACTIVE.set(count)


def get_metrics_output() -> bytes:
    """Return the raw Prometheus text-format metrics buffer."""
    return generate_latest(REGISTRY)


def get_metrics_content_type() -> str:
    """Return the standard Prometheus MIME content type."""
    return str(CONTENT_TYPE_LATEST)


