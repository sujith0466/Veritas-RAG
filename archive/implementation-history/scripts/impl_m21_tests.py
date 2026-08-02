import os
import sys
import subprocess

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

def main():
    print("Starting Milestone 21.4 Implementation (Tests)...")
    os.makedirs("tests/unit/backend/modules/observability", exist_ok=True)
    
    # 1. test_metrics.py
    with open("tests/unit/backend/modules/observability/test_metrics.py", "w") as f:
        f.write("""import pytest
from backend.modules.observability.services.metrics import MetricsRegistry

def test_metrics_registry():
    registry = MetricsRegistry()
    registry.increment_counter("raguard_http_requests_total")
    assert registry.counters["raguard_http_requests_total"] == 1
    
    registry.record_histogram("raguard_http_request_duration_seconds", 0.5)
    assert len(registry.histograms["raguard_http_request_duration_seconds"]) == 1
    
    export = registry.export_metrics()
    assert "raguard_http_requests_total 1" in export
    assert "raguard_http_request_duration_seconds_avg 0.5" in export
""")

    # 2. test_telemetry.py
    with open("tests/unit/backend/modules/observability/test_telemetry.py", "w") as f:
        f.write("""import pytest
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
""")

    print("Created test files.")
    
    print("Running tests...")
    result = subprocess.run([sys.executable, "-m", "pytest", "tests/unit/backend/modules/observability"], capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        sys.exit(1)

    print("Milestone 21.4 completed.")

if __name__ == "__main__":
    main()
