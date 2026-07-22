"""Phase 8 rewrite DTOs — extends Phase 3 baseline with v2 schemas."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Phase 3 baseline — preserved exactly
# ---------------------------------------------------------------------------


class RewriteRequestDTO(BaseModel):
    original_query: str = Field(
        ..., description="The original ambiguous or complex query"
    )
    context_hints: list[str] = Field(
        default_factory=list, description="Optional context hints to guide rewriting"
    )


class DecomposedQueriesDTO(BaseModel):
    original_query: str = Field(..., description="The original query")
    sub_queries: list[str] = Field(
        default_factory=list, description="The decomposed independent search queries"
    )
    is_complex: bool = Field(..., description="True if the query needed decomposition")


class HyDEResponseDTO(BaseModel):
    original_query: str = Field(..., description="The original query")
    hypothetical_document: str = Field(
        ..., description="The generated hypothetical document"
    )
    embedding_query: str = Field(
        ..., description="The combined text used for embedding search"
    )


class ClarificationQuestionDTO(BaseModel):
    question_text: str = Field(
        ..., description="The clarifying question to present to the user"
    )
    options: list[str] = Field(
        default_factory=list,
        description="Suggested multiple choice answers if applicable",
    )


# ---------------------------------------------------------------------------
# Phase 8 — v2 enums and DTOs
# ---------------------------------------------------------------------------


class RewriteStrategy(StrEnum):
    HYDE = "hyde"
    EXPANSION = "expansion"
    DECOMPOSITION = "decomposition"
    ENTITY_RECOVERY = "entity_recovery"
    AUTO = "auto"


class RewriteRequestDTOv2(BaseModel):
    """Phase 8 enriched rewrite request carrying confidence signals."""

    original_query: str = Field(..., min_length=1, max_length=2000)
    tenant_id: str
    strategy_hint: RewriteStrategy = Field(RewriteStrategy.AUTO)
    context_hints: list[str] = Field(default_factory=list)
    conversation_history: list[str] = Field(
        default_factory=list, description="Prior turns for entity resolution"
    )
    domain: str | None = Field(
        None, description="Domain hint for synonym expansion (e.g. 'finance', 'legal')"
    )
    coverage_score: float | None = Field(
        None, ge=0.0, le=1.0, description="Coverage score from ConfidenceEngine"
    )
    uncovered_clauses: list[str] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class EntityResolutionDTO(BaseModel):
    pronoun: str
    resolved_entity: str
    is_resolved: bool
    model_config = ConfigDict(from_attributes=True)


class RewriteResultDTO(BaseModel):
    """Standardized output of any rewrite strategy."""

    original_query: str
    rewritten_query: str
    strategy: RewriteStrategy
    rationale: str
    sub_queries: list[str] = Field(
        default_factory=list, description="Non-empty only for DECOMPOSITION strategy"
    )
    hypothetical_document: str | None = None
    expanded_terms: list[str] = Field(default_factory=list)
    resolved_entities: list[EntityResolutionDTO] = Field(default_factory=list)
    confidence_improvement_estimate: float = Field(0.0, ge=0.0, le=1.0)
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Phase 9 — Clarification Engine schemas and state management
# ---------------------------------------------------------------------------


class ClarificationStatus(StrEnum):
    REQUIRED = "required"
    RESOLVED = "resolved"
    TIMEOUT = "timeout"
    ABORTED = "aborted"


class ClarificationStateDTO(BaseModel):
    """Tracks the state of a paused request waiting for user clarification."""

    correlation_id: str = Field(..., description="Unique request tracking ID")
    tenant_id: str = Field(..., description="Tenant namespace ID")
    original_query: str = Field(..., description="Original user query")
    question_text: str = Field(
        ..., description="Clarification question presented to user"
    )
    options: list[str] = Field(
        default_factory=list, description="Presented multiple choice options"
    )
    status: ClarificationStatus = Field(default=ClarificationStatus.REQUIRED)
    created_at: float = Field(
        ..., description="Timestamp when clarification was requested"
    )
    expires_at: float = Field(
        ..., description="Timestamp when clarification request expires"
    )
    selected_option: str | None = Field(
        default=None, description="User selected resolution option"
    )
    clarified_query: str | None = Field(
        default=None, description="Final resolved query string after clarification"
    )
    model_config = ConfigDict(from_attributes=True)


class ClarificationResumeRequestDTO(BaseModel):
    """Payload submitted by user to resume execution after clarification."""

    correlation_id: str = Field(
        ..., description="Unique request tracking ID corresponding to paused state"
    )
    tenant_id: str = Field(..., description="Tenant namespace ID")
    selected_option: str = Field(
        ...,
        min_length=1,
        description="Option selected or free-text clarification from user",
    )
    additional_context: str | None = Field(
        default=None, description="Optional extra context provided by user"
    )
    model_config = ConfigDict(from_attributes=True)


class ClarifiedQueryDTO(BaseModel):
    """Resolved query package returned when clarification is resumed."""

    correlation_id: str
    original_query: str
    clarified_query: str
    resolution_summary: str
    model_config = ConfigDict(from_attributes=True)
