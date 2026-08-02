import logging

from backend.modules.confidence.schemas.confidence_dto import ConfidenceAction
from backend.modules.retry.schemas.errors import (
    InvalidStateTransition,
    MaxRetriesExceeded,
    NonMonotonicImprovement,
)
from backend.modules.retry.schemas.retry_dto import RetryAttemptDTO, RetryContextDTO, RetryState

logger = logging.getLogger(__name__)

# Minimum improvement threshold to consider a retry monotonically beneficial
MIN_IMPROVEMENT_DELTA = 2.0


class RetryStateMachine:
    """Deterministic Retry State Machine for the RAGuard query lifecycle.

    Enforces:
    - Max 2 retries (hard cap at 3 to avoid agentic loops)
    - Monotonic improvement check on every retry
    - Audited state transitions
    """

    def __init__(self, correlation_id: str, original_query: str, max_retries: int = 2):
        # Enforce the hard cap to prevent agentic instability (per ADR-P3-003)
        enforced_max = min(max_retries, 3)
        self.context = RetryContextDTO(
            correlation_id=correlation_id,
            original_query=original_query,
            max_retries=enforced_max,
        )

    @property
    def state(self) -> RetryState:
        return self.context.current_state

    @property
    def attempt_count(self) -> int:
        return len(self.context.attempts)

    def record_retrieval_complete(self) -> None:
        """Transition from INITIAL -> RETRIEVED."""
        if self.context.current_state not in (RetryState.INITIAL, RetryState.RETRYING):
            raise InvalidStateTransition(
                f"Cannot record retrieval from state: {self.context.current_state}"
            )
        self.context.current_state = RetryState.RETRIEVED
        logger.debug(
            f"[{self.context.correlation_id}] State -> RETRIEVED (attempt {self.attempt_count})"
        )

    def record_confidence_evaluation(
        self,
        confidence_score: float,
        action: ConfidenceAction,
        rewrite_applied: bool = False,
    ) -> None:
        """Transition from RETRIEVED -> CONFIDENCE_EVALUATED and check retry logic."""
        if self.context.current_state != RetryState.RETRIEVED:
            raise InvalidStateTransition(
                f"Cannot evaluate confidence from state: {self.context.current_state}"
            )

        attempt = RetryAttemptDTO(
            attempt_number=self.attempt_count,
            confidence_score=confidence_score,
            state=RetryState.CONFIDENCE_EVALUATED,
            rewrite_applied=rewrite_applied,
        )
        self.context.attempts.append(attempt)
        self.context.current_state = RetryState.CONFIDENCE_EVALUATED

        logger.info(
            f"[{self.context.correlation_id}] Confidence={confidence_score:.2f} action={action} "
            f"attempt={self.attempt_count - 1}/{self.context.max_retries}"
        )

        # Determine next state based on the ConfidenceEngine action
        if action == ConfidenceAction.PROCEED:
            self.context.best_confidence_score = max(
                self.context.best_confidence_score, confidence_score
            )
            self.context.current_state = RetryState.GENERATING

        elif action == ConfidenceAction.RETRY:
            self._try_retry(confidence_score)

        elif action == ConfidenceAction.CLARIFY:
            self.context.current_state = RetryState.CLARIFICATION_REQUESTED

        else:  # ABORT
            self.context.current_state = RetryState.ABORTED

    def _try_retry(self, confidence_score: float) -> None:
        """Attempt a retry after checking budget and monotonic improvement."""
        if self.attempt_count > self.context.max_retries:
            logger.warning(
                f"[{self.context.correlation_id}] Max retries exceeded. Aborting."
            )
            self.context.current_state = RetryState.ABORTED
            raise MaxRetriesExceeded(
                detail={
                    "correlation_id": self.context.correlation_id,
                    "attempts": self.attempt_count,
                    "max_retries": self.context.max_retries,
                }
            )

        # Monotonic improvement check: a retry must improve on the best score so far
        if self.context.best_confidence_score > 0.0:
            improvement = confidence_score - self.context.best_confidence_score
            if improvement < MIN_IMPROVEMENT_DELTA:
                logger.warning(
                    f"[{self.context.correlation_id}] Non-monotonic: score={confidence_score:.2f} "
                    f"vs best={self.context.best_confidence_score:.2f}. Aborting."
                )
                self.context.current_state = RetryState.ABORTED
                raise NonMonotonicImprovement(
                    detail={
                        "correlation_id": self.context.correlation_id,
                        "current_score": confidence_score,
                        "best_score": self.context.best_confidence_score,
                        "delta": improvement,
                    }
                )

        self.context.best_confidence_score = max(
            self.context.best_confidence_score, confidence_score
        )
        self.context.current_state = RetryState.RETRYING
        from backend.observability.metrics import record_retry_metric
        from backend.observability.tracing import trace_retry_controller

        record_retry_metric(strategy="query_rewrite", trigger_reason="low_confidence")
        with trace_retry_controller(
            attempt=self.attempt_count, strategy="query_rewrite"
        ):
            logger.info(
                f"[{self.context.correlation_id}] Retry approved. Moving to RETRYING state."
            )

    def record_generation_complete(self) -> None:
        """Transition from GENERATING -> COMPLETED."""
        if self.context.current_state != RetryState.GENERATING:
            raise InvalidStateTransition(
                f"Cannot complete generation from state: {self.context.current_state}"
            )
        self.context.current_state = RetryState.COMPLETED
        logger.info(f"[{self.context.correlation_id}] State -> COMPLETED")

    def get_context(self) -> RetryContextDTO:
        return self.context
