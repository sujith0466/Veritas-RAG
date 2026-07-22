import time
import uuid

from backend.modules.observability.schemas.observability_dto import \
    TraceSpanDTO


class TelemetryService:
    @staticmethod
    def start_trace(operation_name: str) -> dict:
        trace_id = uuid.uuid4().hex
        span_id = uuid.uuid4().hex[:16]
        return {
            "trace_id": trace_id,
            "span_id": span_id,
            "operation_name": operation_name,
            "start_time": time.time(),
        }

    @staticmethod
    def end_trace(trace_context: dict, status: str = "OK") -> TraceSpanDTO:
        duration_ms = (time.time() - trace_context["start_time"]) * 1000
        return TraceSpanDTO(
            trace_id=trace_context["trace_id"],
            span_id=trace_context["span_id"],
            operation_name=trace_context["operation_name"],
            duration_ms=duration_ms,
            status=status,
        )
