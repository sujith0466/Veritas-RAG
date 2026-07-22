from enum import StrEnum

from pydantic import BaseModel, Field

from backend.modules.confidence.schemas.confidence_dto import \
    ConfidenceResultDTO
from backend.modules.generation.schemas.generation_dto import GroundedAnswerDTO
from backend.modules.reflection.schemas.reflection_dto import \
    ReflectionResultDTO
from backend.modules.retry.schemas.retry_dto import RetryContextDTO


class GatewayOutcome(StrEnum):
    SUCCESS = "SUCCESS"
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"
    ABORTED_LOW_CONFIDENCE = "ABORTED_LOW_CONFIDENCE"
    ABORTED_HALLUCINATION = "ABORTED_HALLUCINATION"
    ABORTED_MAX_RETRIES = "ABORTED_MAX_RETRIES"


class ReliabilityScoreDTO(BaseModel):
    """Unified reliability score compositing all Phase 3 signals."""

    final_score: float = Field(
        ..., ge=0.0, le=100.0, description="Composite reliability score (0-100)"
    )
    confidence_score: float = Field(..., description="Pre-generation confidence score")
    hallucination_score: float = Field(
        ..., description="Post-generation hallucination score (0=safe, 1=hallucinated)"
    )
    is_fully_grounded: bool = Field(
        ..., description="Whether the answer citations are complete"
    )
    is_safe_to_serve: bool = Field(
        ..., description="Whether the reflection engine approved the answer"
    )
    retry_attempts: int = Field(..., description="Number of retry attempts used")


class GatewayRequestDTO(BaseModel):
    query: str = Field(..., description="The user query to process")
    tenant_id: str = Field(..., description="Tenant namespace")
    correlation_id: str = Field(..., description="Request correlation ID")


class GatewayResponseDTO(BaseModel):
    correlation_id: str
    outcome: GatewayOutcome
    answer: GroundedAnswerDTO | None = None
    reliability_score: ReliabilityScoreDTO | None = None
    confidence_result: ConfidenceResultDTO | None = None
    reflection_result: ReflectionResultDTO | None = None
    retry_context: RetryContextDTO | None = None
    clarification_question: str | None = None
    abort_reason: str | None = None


class ScoringInputsDTO(BaseModel):
    retrieval_relevance_score: float = Field(..., ge=0.0, le=1.0)
    validation_entailment_ratio: float = Field(..., ge=0.0, le=1.0)
    confidence_evidence_strength: float = Field(..., ge=0.0, le=1.0)
    reflection_completeness: float = Field(..., ge=0.0, le=1.0)
    unsupported_claim_count: int = Field(0, ge=0)
    invalid_citation_count: int = Field(0, ge=0)


class ScoringRequestDTO(BaseModel):
    correlation_id: str = Field(..., description="Request tracking ID")
    tenant_id: str = Field(..., description="Tenant namespace")
    inputs: ScoringInputsDTO = Field(...)


class ReliabilityScoreDTOv2(BaseModel):
    correlation_id: str = Field(...)
    tenant_id: str = Field(...)
    final_score: float = Field(
        ..., ge=0.0, le=100.0, description="Final reliability score 0-100"
    )
    base_score: float = Field(..., ge=0.0, le=100.0)
    penalty_deduction: float = Field(..., ge=0.0)
    is_trusted: bool = Field(
        ..., description="True if final_score >= 80 and no severe penalties"
    )
    breakdown: dict = Field(
        default_factory=dict, description="Detailed score breakdown"
    )
