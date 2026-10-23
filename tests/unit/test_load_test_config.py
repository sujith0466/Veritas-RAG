"""Unit tests for Load Testing Configuration and NIST Type 7 Statistical Engine.

WP-3D: TSK-3D-02 — Locust Load Testing Harness.
"""

import numpy as np
import pytest

from tests.performance.load.config import (
    LoadTestConfig,
    calculate_percentiles_nist_type7,
    evaluate_load_benchmark_results,
)


def test_calculate_percentiles_nist_type7_linear_interpolation():
    """Verify NIST Type 7 percentiles match expected mathematical interpolation."""
    # Simple deterministic dataset: [100.0, 200.0, 300.0, 400.0, 500.0]
    samples = [100.0, 200.0, 300.0, 400.0, 500.0]
    percentiles = calculate_percentiles_nist_type7(samples, percentiles=(50.0, 90.0, 95.0, 99.0))

    assert percentiles[50.0] == 300.0
    assert percentiles[90.0] == 460.0
    assert percentiles[95.0] == 480.0
    assert percentiles[99.0] == 496.0


def test_calculate_percentiles_empty_samples():
    """Verify empty samples sequence returns zeroed percentiles gracefully."""
    percentiles = calculate_percentiles_nist_type7([], percentiles=(50.0, 95.0))
    assert percentiles[50.0] == 0.0
    assert percentiles[95.0] == 0.0


def test_evaluate_load_benchmark_results_pass():
    """Verify evaluate_load_benchmark_results returns overall_pass=True for compliant metrics."""
    # 600 samples under 500ms
    rest_latencies = [150.0] * 600
    ttft_latencies = [350.0] * 100

    results = evaluate_load_benchmark_results(
        rest_latencies_ms=rest_latencies,
        ttft_latencies_ms=ttft_latencies,
        total_streams=100,
        dropped_streams=0,
        http_5xx_count=0,
        total_requests=600,
    )

    assert results["overall_pass"] is True
    assert results["min_samples_met"] is True
    assert results["passes_p95_rest"] is True
    assert results["passes_p95_ttft"] is True
    assert results["passes_stream_drops"] is True
    assert results["passes_5xx_rate"] is True


def test_evaluate_load_benchmark_results_fail_on_drops():
    """Verify evaluate_load_benchmark_results fails if any streams drop."""
    rest_latencies = [150.0] * 600
    ttft_latencies = [350.0] * 100

    results = evaluate_load_benchmark_results(
        rest_latencies_ms=rest_latencies,
        ttft_latencies_ms=ttft_latencies,
        total_streams=100,
        dropped_streams=1,  # 1% drop rate > 0.0%
        http_5xx_count=0,
        total_requests=600,
    )

    assert results["overall_pass"] is False
    assert results["passes_stream_drops"] is False
