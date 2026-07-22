from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from backend.modules.observability.services.metrics import MetricsRegistry

router = APIRouter(prefix="/observability/v1", tags=["Observability"])


@router.get("/metrics", response_class=PlainTextResponse)
async def get_metrics():
    registry = MetricsRegistry.get_instance()
    return registry.export_metrics()
