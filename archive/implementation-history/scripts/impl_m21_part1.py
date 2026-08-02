import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

def main():
    print("Starting Milestone 21.1 Implementation...")
    
    dirs = [
        "backend/modules/observability/schemas",
        "backend/modules/observability/services",
        "backend/modules/observability/api"
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
        init_file = f"{d}/__init__.py"
        if not os.path.exists(init_file):
            with open(init_file, "w") as f:
                pass
    with open("backend/modules/observability/__init__.py", "w") as f:
        pass

    # 1. observability_dto.py
    with open("backend/modules/observability/schemas/observability_dto.py", "w") as f:
        f.write("""from pydantic import BaseModel
from typing import Dict, Any, List

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
""")

    # 2. api/metrics_routes.py
    with open("backend/modules/observability/api/metrics_routes.py", "w") as f:
        f.write("""from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from backend.modules.observability.services.metrics import MetricsRegistry

router = APIRouter(prefix="/observability/v1", tags=["Observability"])

@router.get("/metrics", response_class=PlainTextResponse)
async def get_metrics():
    registry = MetricsRegistry.get_instance()
    return registry.export_metrics()
""")

    print("Milestone 21.1 completed.")

if __name__ == "__main__":
    main()
