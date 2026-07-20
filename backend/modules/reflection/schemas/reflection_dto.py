from enum import StrEnum
from pydantic import BaseModel, Field
from backend.modules.generation.schemas.generation_dto import GroundedAnswerDTO


class ClaimVerdict(StrEnum):
    SUPPORTED = "SUPPORTED"       # Claim is backed by citation excerpt
    UNSUPPORTED = "UNSUPPORTED"   # Claim has no clear evidential support
    CONTRADICTED = "CONTRADICTED" # Claim directly conflicts with a citation


class ClaimValidationResultDTO(BaseModel):
    claim_text: str = Field(..., description="The extracted claim sentence from the answer")
    verdict: ClaimVerdict = Field(..., description="Validation verdict")
    citation_index: int | None = Field(None, description="The citation [N] index that this claim references")
    supporting_excerpt: str | None = Field(None, description="The excerpt from the citation that supports/contradicts the claim")


class ReflectionRequestDTO(BaseModel):
    grounded_answer: GroundedAnswerDTO = Field(..., description="The generated grounded answer to reflect on")
    correlation_id: str = Field(..., description="Request tracking ID")


class ReflectionResultDTO(BaseModel):
    correlation_id: str = Field(..., description="Request tracking ID")
    overall_verdict: ClaimVerdict = Field(..., description="Worst-case verdict across all claims")
    hallucination_score: float = Field(..., ge=0.0, le=1.0, description="Ratio of unsupported/contradicted claims (0 = fully grounded, 1 = fully hallucinated)")
    claim_results: list[ClaimValidationResultDTO] = Field(default_factory=list)
    is_safe_to_serve: bool = Field(..., description="True if hallucination_score < 0.3 and no CONTRADICTED claims")

class CompletenessReportDTO(BaseModel):
    score: float = Field(..., ge=0.0, le=1.0, description="Ratio of addressed query requirements")
    addressed_clauses: list[str] = Field(default_factory=list)
    unaddressed_clauses: list[str] = Field(default_factory=list)

class LogicalReviewReportDTO(BaseModel):
    consistency_score: float = Field(..., ge=0.0, le=1.0, description="Score reflecting internal logical soundness")
    contradictions_found: list[str] = Field(default_factory=list)

class ReflectionRequestDTOv2(BaseModel):
    grounded_answer: GroundedAnswerDTO = Field(..., description="The generated grounded answer to reflect on")
    original_query: str = Field(..., description="The original user query text")
    correlation_id: str = Field(..., description="Request tracking ID")
    tenant_id: str = Field(..., description="Tenant namespace")

class ReflectionScoreDTO(BaseModel):
    hallucination_score: float = Field(..., ge=0.0, le=1.0)
    completeness_score: float = Field(..., ge=0.0, le=1.0)
    consistency_score: float = Field(..., ge=0.0, le=1.0)

class ReflectionResultDTOv2(BaseModel):
    correlation_id: str = Field(..., description="Request tracking ID")
    tenant_id: str = Field(..., description="Tenant namespace")
    overall_verdict: ClaimVerdict = Field(..., description="Worst-case verdict across all claims")
    scores: ReflectionScoreDTO = Field(..., description="Component reflection scores")
    claim_results: list[ClaimValidationResultDTO] = Field(default_factory=list)
    completeness_report: CompletenessReportDTO = Field(..., description="Query coverage breakdown")
    logical_report: LogicalReviewReportDTO = Field(..., description="Internal contradiction details")
    is_safe_to_serve: bool = Field(..., description="True if no severe issues detected")
    attempt_number: int = Field(1, description="Pass attempt number")
