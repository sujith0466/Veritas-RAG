from fastapi import APIRouter

from backend.modules.intelligence.schemas.intelligence_dto import (
    FeedbackEventDTO, IntelligenceInsightDTO, OptimizationRecommendationDTO)

router = APIRouter(prefix="/intelligence/v1", tags=["Intelligence"])


@router.post("/feedback", response_model=dict)
async def submit_feedback(event: FeedbackEventDTO):
    # In a real implementation, this forwards to FeedbackProcessor
    return {"status": "accepted"}


@router.get("/insights/{tenant_id}", response_model=IntelligenceInsightDTO)
async def get_insights(tenant_id: str):
    return IntelligenceInsightDTO(
        tenant_id=tenant_id,
        recommendations=[
            OptimizationRecommendationDTO(
                parameter_name="similarity_threshold",
                current_value=0.75,
                recommended_value=0.72,
                confidence_score=0.88,
                reason="High volume of false negatives on long-tail queries.",
            )
        ],
        suggested_actions=["Re-index vector space due to drift"],
    )
