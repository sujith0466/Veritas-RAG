import pytest
from backend.modules.observability.services.telemetry import TelemetryService
from backend.modules.observability.middleware import TelemetryMiddleware
from backend.modules.observability.services.metrics import MetricsRegistry
import time

def test_telemetry_service():
    ctx = TelemetryService.start_trace("test_op")
    assert "trace_id" in ctx
    time.sleep(0.01)
    span = TelemetryService.end_trace(ctx, "OK")
    assert span.duration_ms > 0
    assert span.operation_name == "test_op"

@pytest.mark.asyncio
async def test_telemetry_middleware():
    registry = MetricsRegistry()
    middleware = TelemetryMiddleware(registry)
    span = await middleware.process_request("/api/v1/test")
    assert span.status == "OK"
    assert registry.counters["raguard_http_requests_total"] == 1
