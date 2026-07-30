from pydantic import BaseModel, ConfigDict, Field

from backend.modules.retrieval.schemas.retrieval_dto import RankedEvidenceDTO


class CitationDTO(BaseModel):
    citation_index: int = Field(
        ...,
        description="1-based index of the citation marker in the answer text, e.g. [1]",
    )
    chunk_id: str = Field(..., description="The source chunk ID")
    document_id: str = Field(..., description="The source document ID")
    source_name: str | None = Field(None, description="Human-readable filename or source")
    document_name: str | None = Field(None, description="Human-readable document name")
    excerpt: str = Field(
        ..., description="Verbatim excerpt from the chunk that supports the cited claim"
    )
    relevance_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Relevance of this citation to the cited claim",
    )


class GenerationRequestDTO(BaseModel):
    query: str = Field(..., description="The user's original or rewritten query")
    evidence_chunks: list[dict] = Field(
        ...,
        description="List of evidence chunks (id, content, document_id) to generate from",
    )
    correlation_id: str = Field(..., description="Request tracking ID for tracing")
    max_answer_tokens: int = Field(
        default=1024,
        ge=64,
        le=4096,
        description="Max token budget for the generated answer",
    )


class GroundedAnswerDTO(BaseModel):
    answer_text: str = Field(
        ...,
        description="The generated answer with inline citation markers e.g. [1], [2]",
    )
    citations: list[CitationDTO] = Field(
        default_factory=list,
        description="Ordered list of citations matching inline markers",
    )
    is_fully_grounded: bool = Field(
        ...,
        description="True if every sentence in the answer has at least one citation",
    )
    correlation_id: str = Field(..., description="Request tracking ID")
    evidence_used_count: int = Field(
        ..., description="Number of evidence chunks used in the answer"
    )


# ---------------------------------------------------------------------------
# Phase 10 — v2 Schemas, Prompt Guardrails, and Streaming DTOs
# ---------------------------------------------------------------------------


class PromptGuardrailConfigDTO(BaseModel):
    """Configuration for prompt injection guardrails and strict grounding."""

    enable_injection_check: bool = Field(
        default=True,
        description="Whether to scan evidence chunks for prompt injection attempts",
    )
    strict_grounding_enforcement: bool = Field(
        default=True, description="If True, raise error or flag ungrounded claims"
    )
    custom_system_prompt: str | None = Field(
        default=None, description="Optional custom instructions to prepend"
    )
    max_citations_per_sentence: int = Field(default=3, ge=1, le=10)
    model_config = ConfigDict(from_attributes=True)


class GenerationRequestDTOv2(BaseModel):
    """Phase 10 enriched generation request with tenant, streaming, and guardrail options."""

    query: str = Field(..., min_length=1, max_length=2000)
    evidence_chunks: list[RankedEvidenceDTO] = Field(
        ..., description="List of retrieved canonical evidence chunks"
    )
    correlation_id: str = Field(..., description="Tracing ID")
    tenant_id: str = Field(..., description="Tenant namespace ID")
    max_answer_tokens: int = Field(default=1024, ge=64, le=4096)
    temperature: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Low temperature for factual generation",
    )
    stream: bool = Field(
        default=False, description="Whether to stream response via Server-Sent Events"
    )
    guardrail_config: PromptGuardrailConfigDTO = Field(
        default_factory=PromptGuardrailConfigDTO
    )
    model_config = ConfigDict(from_attributes=True)


class StreamingGenerationChunkDTO(BaseModel):
    """Single SSE stream delta chunk."""

    chunk_index: int = Field(..., ge=0)
    text_delta: str
    citations_delta: list[CitationDTO] = Field(default_factory=list)
    is_final: bool = Field(default=False)
    correlation_id: str
    is_fully_grounded: bool | None = Field(
        default=None, description="Evaluated on final chunk"
    )
    model_config = ConfigDict(from_attributes=True)
