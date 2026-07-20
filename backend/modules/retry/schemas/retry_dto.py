"""Retry Controller DTOs — Phase 3 baseline + Phase 7 extensions."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from backend.modules.confidence.schemas.confidence_dto import ConfidenceResultDTOv2


# ---------------------------------------------------------------------------
# Phase 3 — preserved exactly
# ---------------------------------------------------------------------------

class RetryState(StrEnum):
    INITIAL = "INITIAL"
    RETRIEVED = "RETRIEVED"
    CONFIDENCE_EVALUATED = "CONFIDENCE_EVALUATED"
    RETRYING = "RETRYING"
    GENERATING = "GENERATING"
    COMPLETED = "COMPLETED"
    CLARIFICATION_REQUESTED = "CLARIFICATION_REQUESTED"
    ABORTED = "ABORTED"


class RetryAttemptDTO(BaseModel):
    attempt_number: int = Field(..., description="The attempt index (0-indexed)")
    confidence_score: float = Field(..., ge=0.0, le=100.0, description="Confidence score achieved on this attempt")
    state: RetryState = Field(..., description="The state of the machine after this attempt")
    rewrite_applied: bool = Field(default=False, description="Whether a query rewrite was applied on this attempt")


class RetryContextDTO(BaseModel):
    correlation_id: str = Field(..., description="Request correlation ID")
    original_query: str = Field(..., description="Original query before any rewrites")
    max_retries: int = Field(default=2, ge=1, le=3, description="Maximum allowed retry attempts (default 2, enforced cap at 3)")
    attempts: list[RetryAttemptDTO] = Field(default_factory=list, description="Audit trail of all attempts")
    current_state: RetryState = Field(default=RetryState.INITIAL, description="Current machine state")
    best_confidence_score: float = Field(default=0.0, ge=0.0, le=100.0, description="Best confidence score seen across all attempts")


# ---------------------------------------------------------------------------
# Phase 7 — new enums and DTOs
# ---------------------------------------------------------------------------

class RetryReason(StrEnum):
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    LLM_API_ERROR = "LLM_API_ERROR"
    RATE_LIMIT = "RATE_LIMIT"
    TIMEOUT = "TIMEOUT"
    MALFORMED_OUTPUT = "MALFORMED_OUTPUT"
    UNKNOWN = "UNKNOWN"


class RetryAction(StrEnum):
    RETRY_IMMEDIATE = "RETRY_IMMEDIATE"
    RETRY_WITH_BACKOFF = "RETRY_WITH_BACKOFF"
    RETRY_WITH_REWRITE = "RETRY_WITH_REWRITE"
    RETRY_WITH_FALLBACK_MODEL = "RETRY_WITH_FALLBACK_MODEL"
    ABORT = "ABORT"


class RetryRuleDTO(BaseModel):
    reason: RetryReason
    action: RetryAction
    base_backoff_ms: int = Field(..., ge=0)
    max_attempts_for_rule: int = Field(..., ge=0)
    model_config = ConfigDict(from_attributes=True)


class RetryPolicyDTO(BaseModel):
    tenant_id: str
    max_total_retries: int = Field(3, le=3, description="Hard cap from PRD: max 3 retries")
    rules: list[RetryRuleDTO] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)


class RetryRequestContextDTO(BaseModel):
    """Context object fed into the Phase 7 Decision Engine (distinct from Phase 3 RetryContextDTO)."""
    query_id: str = Field(..., description="Unique request/query ID for this pipeline run")
    tenant_id: str
    attempt_number: int = Field(..., ge=1, le=4, description="Current attempt (1-based; >3 triggers budget exhaustion)")
    reason: RetryReason
    last_confidence_score: float | None = Field(default=None, ge=0.0, le=100.0)
    error_message: str | None = None
    model_config = ConfigDict(from_attributes=True)


class RetryDecisionDTO(BaseModel):
    """Output of the Phase 7 Decision Engine."""
    action: RetryAction
    backoff_ms: int = Field(0, ge=0, le=30000)
    reason_code: str
    is_budget_exhausted: bool = False
    is_monotonic_regression: bool = False
    model_config = ConfigDict(from_attributes=True)

