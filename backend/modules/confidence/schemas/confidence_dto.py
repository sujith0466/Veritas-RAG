from enum import StrEnum

from pydantic import BaseModel, Field

from backend.modules.reliability.schemas.reliability_dto import \
    ReliableRetrievalResultDTO


class ConfidenceAction(StrEnum):
    PROCEED = "PROCEED"
    RETRY = "RETRY"
    CLARIFY = "CLARIFY"
    ABORT = "ABORT"


class ConfidenceEvalRequestDTO(BaseModel):
    query: str = Field(..., description="The user's query to evaluate evidence against")
    retrieval_result: ReliableRetrievalResultDTO = Field(
        ...,
        description="The reliable retrieval result containing evidence and SLA flags",
    )


class CoverageMetricsDTO(BaseModel):
    coverage_score: float = Field(
        ..., ge=0.0, le=1.0, description="Clause-level token overlap score (0.0 to 1.0)"
    )
    clauses_covered: int = Field(
        ..., description="Number of query clauses covered by evidence"
    )
    total_clauses: int = Field(
        ..., description="Total number of clauses extracted from the query"
    )


class ContradictionReportDTO(BaseModel):
    contradiction_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Probability of contradictory claims in evidence (0.0 means no contradiction, 1.0 means strong contradiction)",
    )
    contradictory_pairs: list[dict] = Field(
        default_factory=list, description="Pairs of chunk IDs identified as conflicting"
    )


class FreshnessReportDTO(BaseModel):
    freshness_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Temporal decay score based on document timestamps (1.0 is perfectly fresh)",
    )
    oldest_chunk_age_days: float | None = Field(
        None, description="Age of the oldest evidence chunk in days"
    )


class ConfidenceResultDTO(BaseModel):
    score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="The final pre-generation confidence score (0-100)",
    )
    action: ConfidenceAction = Field(
        ..., description="The threshold-based action to take"
    )
    coverage_metrics: CoverageMetricsDTO
    contradiction_report: ContradictionReportDTO
    freshness_report: FreshnessReportDTO
    is_degraded: bool = Field(
        ...,
        description="True if the score was adjusted due to degraded fallback telemetry",
    )
