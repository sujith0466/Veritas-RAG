from pydantic import BaseModel
from typing import List, Optional

class FeedbackEventDTO(BaseModel):
    query_id: str
    tenant_id: str
    feedback_type: str  # "THUMBS_UP", "THUMBS_DOWN", "IMPLICIT_DWELL"
    metadata: Optional[dict] = None

class OptimizationRecommendationDTO(BaseModel):
    parameter_name: str
    current_value: float
    recommended_value: float
    confidence_score: float
    reason: str

class IntelligenceInsightDTO(BaseModel):
    tenant_id: str
    recommendations: List[OptimizationRecommendationDTO]
    suggested_actions: List[str]
