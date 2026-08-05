from uuid import UUID

from pydantic import BaseModel


class DimensionScoreDTO(BaseModel):
    """Breakdown of individual score calculation details."""

    score: float
    weight: float
    raw_metric: float
    description: str


class KnowledgeHealthScoreDTO(BaseModel):
    """Overall health score and tier classification for a workspace."""

    workspace_id: UUID
    overall_score: float
    tier: str  # EXCELLENT, GOOD, DEGRADED, CRITICAL

    # Dimension sub-scores
    coverage: DimensionScoreDTO
    freshness: DimensionScoreDTO
    quality: DimensionScoreDTO
    reliability: DimensionScoreDTO

    prioritized_recommendations: list[str]
