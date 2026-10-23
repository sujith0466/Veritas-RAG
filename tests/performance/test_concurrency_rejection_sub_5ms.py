"""Verification of Concurrency Limiter Request 51 Shedding and Memory Safety Guards.

WP-3D: TSK-3D-03 — Saturation & Queue Stress Harness.

Asserts:
1. Concurrency limiter Request 51 shedding (<5ms internal middleware dispatch).
2. HTTP 503 response with 'Retry-After: 5' header.
3. Memory limit discovery and 90% threshold calculation (921.6 MiB for 1.0 GiB limit).
4. Fail-closed behavior on unresolvable container.
"""

import asyncio
import time

from fastapi import FastAPI
from fastapi.responses import JSONResponse, StreamingResponse
import pytest
from starlette.requests import Request

from backend.core.middleware.concurrency import SSEConcurrencyLimiterMiddleware
from tests.performance.stress.stress_test import (
    MemoryDiscoveryFailure,
    calculate_memory_abort_threshold,
    discover_container_memory_limit,
)


@pytest.fixture
def app_with_concurrency_limiter():
    """Create a test FastAPI app wrapped with SSEConcurrencyLimiterMiddleware capped at 50."""
    app = FastAPI()

    # Wrap with concurrency limiter set to exactly 50 streams
    app.add_middleware(SSEConcurrencyLimiterMiddleware, max_concurrent_streams=50)

    @app.post("/api/v1/chat/sessions/{session_id}/stream")
    async def fake_stream(session_id: str):
        async def event_generator():
            yield "data: chunk 1\n\n"
            await asyncio.sleep(0.5)
            yield "data: chunk 2\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    return app


@pytest.mark.asyncio
async def test_concurrency_rejection_sub_5ms(app_with_concurrency_limiter):
    """Verify that when 50 streams are active, Request 51 is rejected in <5ms with HTTP 503."""
    async def dummy_app(scope, receive, send):
        response = JSONResponse({"status": "ok"})
        await response(scope, receive, send)

    limiter = SSEConcurrencyLimiterMiddleware(dummy_app, max_concurrent_streams=50)
    # Artificially saturate active streams to 50
    limiter._active_streams = 50

    # Simulate Request 51
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/chat/sessions/test-session-123/stream",
        "headers": [(b"accept", b"text/event-stream")],
    }
    request = Request(scope)

    async def call_next(req):
        return JSONResponse({"status": "should_not_reach"})

    # Warm-up call to avoid one-off initialization timing
    await limiter.dispatch(request, call_next)

    # Measure internal dispatch latency
    start = time.perf_counter()
    response = await limiter.dispatch(request, call_next)
    dispatch_time_ms = (time.perf_counter() - start) * 1000.0

    # Assertions
    assert response.status_code == 503
    assert response.headers.get("Retry-After") == "5"
    assert "detail" in response.body.decode("utf-8")
    assert "Too many concurrent streaming connections" in response.body.decode("utf-8")
    # Master Plan Section 7.1 requirement: internal dispatch latency < 5ms
    assert dispatch_time_ms < 5.0, f"Internal dispatch latency was {dispatch_time_ms:.3f}ms (must be < 5.0ms)"


def test_calculate_memory_abort_threshold_1gib():
    """Verify 90% threshold for 1.0 GiB limit calculates to exactly 921.6 MiB."""
    limit_1gib = 1024 * 1024 * 1024  # 1,073,741,824 bytes
    threshold = calculate_memory_abort_threshold(limit_1gib, 0.90)

    expected_bytes = int(limit_1gib * 0.90)  # 966,367,641 bytes
    assert threshold == expected_bytes
    assert abs((threshold / (1024 * 1024)) - 921.6) < 0.1


def test_calculate_memory_abort_threshold_invalid():
    """Verify calculate_memory_abort_threshold raises ValueError on non-positive input."""
    with pytest.raises(ValueError, match="Memory limit bytes must be positive"):
        calculate_memory_abort_threshold(0)


def test_discover_container_memory_limit_fail_closed():
    """Verify non-existent container raises MemoryDiscoveryFailure (Fail-Closed)."""
    with pytest.raises(MemoryDiscoveryFailure, match="CRITICAL SAFETY ABORT"):
        discover_container_memory_limit("non_existent_container_xyz_999")
