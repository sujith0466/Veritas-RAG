import time
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
