"""Load Testing Configuration and Statistical Metrics Engine.

WP-3D: TSK-3D-02 — Locust Load Testing Harness.

Adheres strictly to Master Plan Section 7.1, 10.2, and 12:
- Statistical standard: NIST / Hyndman-Fan Type 7 linear interpolation (np.percentile(method='linear')).
- Sample size threshold: N >= 500 valid samples with 60s warm-up discarded.
- Operational budgets: REST p95 < 500ms, p99 < 1500ms, 0.0% 5xx errors.
- Streaming budgets: 50 concurrent SSE streams, 0.0% stream drops, nominal p95 TTFT < 800ms.
"""

from dataclasses import dataclass
import os
from typing import Sequence

import numpy as np


@dataclass(frozen=True)
class LoadTestConfig:
    """Configuration parameters for headless and distributed Locust test runs."""

    # Target Endpoint — requires explicit opt-in; silent default to localhost:8000 prohibited
    host: str | None = os.getenv("PERF_TARGET_HOST")

    # Preflight Operator Safeguard Confirmations
    confirm_target_url: bool = os.getenv("PERF_CONFIRM_TARGET_URL", "false").lower() == "true"
    confirm_disposable_stores: bool = os.getenv("PERF_CONFIRM_DISPOSABLE_STORES", "false").lower() == "true"
    confirm_mock_provider: bool = os.getenv("PERF_CONFIRM_MOCK_PROVIDER", "false").lower() == "true"

    # Attestation Credentials (optional admin token to query trusted detailed health endpoint)
    admin_token: str | None = os.getenv("PERF_ADMIN_TOKEN")

    # Safe Fixture Cleanup
    enable_fixture_cleanup: bool = os.getenv("PERF_ENABLE_FIXTURE_CLEANUP", "true").lower() == "true"

    # Authentication Credentials (QA Tenant)
    qa_email: str = os.getenv("QA_EMAIL", "qa@raguard.ai")
    qa_password: str = os.getenv("QA_PASSWORD", "RaguardQA2026!")

    # Concurrency and Pacing
    target_users: int = int(os.getenv("PERF_TARGET_USERS", "50"))
    spawn_rate: float = float(os.getenv("PERF_SPAWN_RATE", "5.0"))
    run_time_seconds: int = int(os.getenv("PERF_RUN_TIME_SECONDS", "180"))
    warmup_seconds: float = float(os.getenv("PERF_WARMUP_SECONDS", "60.0"))

    # Statistical Thresholds
    min_samples: int = int(os.getenv("PERF_MIN_SAMPLES", "500"))
    p95_rest_latency_ms: float = 500.0
    p99_rest_latency_ms: float = 1500.0
    nominal_p95_ttft_ms: float = 800.0
    saturated_p95_ttft_ms: float = 1200.0
    max_stream_drop_rate: float = 0.0
    max_5xx_rate: float = 0.0


def calculate_percentiles_nist_type7(
    samples: Sequence[float],
    percentiles: Sequence[float] = (50.0, 90.0, 95.0, 99.0),
) -> dict[float, float]:
    """Calculate percentiles using NIST / Hyndman-Fan Type 7 linear interpolation.

    Master Plan Section 7.1 explicitly mandates Type 7 linear interpolation to eliminate
    unsupported or biased nearest-rank percentiles.

    Args:
        samples: Sequence of floating-point latency or TTFT observations.
        percentiles: Percentile ranks to compute (e.g., [50.0, 95.0, 99.0]).

    Returns:
        Mapping of percentile rank to interpolated value. Empty dict if samples is empty.
    """
    if not samples:
        return {p: 0.0 for p in percentiles}

    arr = np.asarray(samples, dtype=np.float64)
    # np.percentile with method="linear" implements Hyndman and Fan Type 7
    results = np.percentile(arr, percentiles, method="linear")

    return {p: float(val) for p, val in zip(percentiles, results, strict=False)}


def evaluate_load_benchmark_results(
    rest_latencies_ms: Sequence[float],
    ttft_latencies_ms: Sequence[float],
    total_streams: int,
    dropped_streams: int,
    http_5xx_count: int,
    total_requests: int,
) -> dict[str, bool | float | int | dict[float, float]]:
    """Evaluate benchmark measurements against canonical Master Plan thresholds."""
    config = LoadTestConfig()

    rest_percentiles = calculate_percentiles_nist_type7(rest_latencies_ms)
    ttft_percentiles = calculate_percentiles_nist_type7(ttft_latencies_ms)

    stream_drop_rate = (
        (dropped_streams / total_streams) if total_streams > 0 else 0.0
    )
    http_5xx_rate = (
        (http_5xx_count / total_requests) if total_requests > 0 else 0.0
    )

    p95_rest = rest_percentiles.get(95.0, 0.0)
    p99_rest = rest_percentiles.get(99.0, 0.0)
    p95_ttft = ttft_percentiles.get(95.0, 0.0)

    # Compliance checks
    passes_p95_rest = p95_rest <= config.p95_rest_latency_ms
    passes_p99_rest = p99_rest <= config.p99_rest_latency_ms
    passes_p95_ttft = p95_ttft <= config.nominal_p95_ttft_ms
    passes_stream_drops = stream_drop_rate <= config.max_stream_drop_rate
    passes_5xx_rate = http_5xx_rate <= config.max_5xx_rate

    overall_pass = (
        passes_p95_rest
        and passes_p99_rest
        and passes_p95_ttft
        and passes_stream_drops
        and passes_5xx_rate
        and len(rest_latencies_ms) >= config.min_samples
    )

    return {
        "overall_pass": overall_pass,
        "sample_count": len(rest_latencies_ms),
        "min_samples_met": len(rest_latencies_ms) >= config.min_samples,
        "rest_percentiles": rest_percentiles,
        "ttft_percentiles": ttft_percentiles,
        "stream_drop_rate": stream_drop_rate,
        "http_5xx_rate": http_5xx_rate,
        "passes_p95_rest": passes_p95_rest,
        "passes_p99_rest": passes_p99_rest,
        "passes_p95_ttft": passes_p95_ttft,
        "passes_stream_drops": passes_stream_drops,
        "passes_5xx_rate": passes_5xx_rate,
    }
