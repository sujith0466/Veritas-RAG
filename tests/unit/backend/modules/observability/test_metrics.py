import pytest
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
