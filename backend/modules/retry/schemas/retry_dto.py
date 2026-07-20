from enum import StrEnum
from pydantic import BaseModel, Field


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
