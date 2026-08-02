import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

def main():
    print("Starting Milestone 21.3 Implementation...")
    
    # 1. telemetry.py
    with open("backend/modules/observability/services/telemetry.py", "w") as f:
        f.write("""import uuid
import time
from backend.modules.observability.schemas.observability_dto import TraceSpanDTO

class TelemetryService:
    @staticmethod
    def start_trace(operation_name: str) -> dict:
        trace_id = uuid.uuid4().hex
        span_id = uuid.uuid4().hex[:16]
        return {
            "trace_id": trace_id,
            "span_id": span_id,
            "operation_name": operation_name,
            "start_time": time.time()
        }

    @staticmethod
    def end_trace(trace_context: dict, status: str = "OK") -> TraceSpanDTO:
        duration_ms = (time.time() - trace_context["start_time"]) * 1000
        return TraceSpanDTO(
            trace_id=trace_context["trace_id"],
            span_id=trace_context["span_id"],
            operation_name=trace_context["operation_name"],
            duration_ms=duration_ms,
            status=status
        )
""")

    # 2. middleware.py
    with open("backend/modules/observability/middleware.py", "w") as f:
        f.write("""import time
from backend.modules.observability.services.telemetry import TelemetryService
from backend.modules.observability.services.metrics import MetricsRegistry

class TelemetryMiddleware:
    def __init__(self, registry: MetricsRegistry):
        self.registry = registry

    async def process_request(self, path: str):
        # Start trace
        trace_context = TelemetryService.start_trace(f"HTTP GET {path}")
        
        # Simulate processing time
        await self._mock_process()
        
        # End trace
        span = TelemetryService.end_trace(trace_context, "OK")
        
        # Record metrics
        self.registry.increment_counter("raguard_http_requests_total")
        self.registry.record_histogram("raguard_http_request_duration_seconds", span.duration_ms / 1000.0)
        
        return span

    async def _mock_process(self):
        import asyncio
        await asyncio.sleep(0.01)
""")

    print("Milestone 21.3 completed.")

if __name__ == "__main__":
    main()
