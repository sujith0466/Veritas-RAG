from fastapi import APIRouter

from backend.modules.analytics.schemas.analytics_dto import (ROIAttributionDTO,
                                                             TrendForecastDTO)

router = APIRouter(prefix="/analytics/v1/roi", tags=["ROI"])


@router.get("/{tenant_id}", response_model=ROIAttributionDTO)
async def get_roi(tenant_id: str):
    return ROIAttributionDTO(
        tenant_id=tenant_id,
        window_days=30,
        queries_trusted=1000,
        hallucinations_blocked=10,
        ticket_savings_usd=18500.0,
        incident_savings_usd=2500.0,
        total_llm_cost_usd=50.0,
        net_roi_usd=20950.0,
    )


@router.get("/{tenant_id}/forecast", response_model=TrendForecastDTO)
async def get_forecast(tenant_id: str):
    return TrendForecastDTO(
        tenant_id=tenant_id, projected_cost_90d_usd=150.0, projected_tokens_90d=30000000
    )
