from enum import StrEnum

from pydantic import BaseModel, Field

from backend.modules.generation.schemas.generation_dto import GroundedAnswerDTO


class EntailmentVerdict(StrEnum):
    ENTAILED = "ENTAILED"
    NEUTRAL = "NEUTRAL"
    CONTRADICTED = "CONTRADICTED"


class ClaimValidationItemDTO(BaseModel):
    claim_text: str = Field(
        ..., description="The atomic claim extracted from the answer"
    )
    citation_index: int | None = Field(
        None, description="The citation index it references"
    )
    excerpt: str | None = Field(None, description="The excerpt used for NLI evaluation")
    verdict: EntailmentVerdict = Field(..., description="NLI evaluation verdict")
    confidence_score: float = Field(
        ..., ge=0.0, le=1.0, description="Model confidence in verdict"
    )


class ValidationRequestDTO(BaseModel):
    grounded_answer: GroundedAnswerDTO = Field(
        ..., description="The generated grounded answer"
    )
    correlation_id: str = Field(..., description="Request tracking ID")
    tenant_id: str = Field(..., description="Tenant namespace")


class ValidationResultDTO(BaseModel):
    correlation_id: str = Field(..., description="Request tracking ID")
    tenant_id: str = Field(..., description="Tenant namespace")
    overall_verdict: EntailmentVerdict = Field(
        ..., description="Aggregated worst-case verdict"
    )
    entailment_ratio: float = Field(
        ..., ge=0.0, le=1.0, description="Ratio of ENTAILED claims"
    )
    unsupported_claim_count: int = Field(
        ..., description="Number of NEUTRAL or CONTRADICTED claims"
    )
    invalid_citation_count: int = Field(
        ..., description="Number of claims referencing missing citations"
    )
    claim_details: list[ClaimValidationItemDTO] = Field(default_factory=list)
    is_valid: bool = Field(
        ..., description="True if no contradictions and entailment_ratio >= threshold"
    )
