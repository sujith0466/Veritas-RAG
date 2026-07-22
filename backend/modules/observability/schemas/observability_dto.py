from pydantic import BaseModel


class TraceSpanDTO(BaseModel):
    trace_id: str
    span_id: str
    operation_name: str
    duration_ms: float
    status: str


class OperationalMetricsSummaryDTO(BaseModel):
    active_requests: int
    error_rate_5m: float
    avg_latency_ms: float
    cpu_utilization_pct: float
