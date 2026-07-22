"""Retry Controller (ExecutionGateway v2) — Phase 7.

Wraps the DecisionEngine with monotonicity tracking and backoff sleep.
Designed to be consumed by downstream Phase 8 (Query Rewrite) and Phase 9 (Clarification).
"""

import asyncio

from backend.modules.retry.schemas.retry_dto import (RetryAction,
                                                     RetryDecisionDTO,
                                                     RetryRequestContextDTO)
from backend.modules.retry.services.decision_engine import DecisionEngine


class RetryController:
    """Phase 7 ExecutionGateway v2 — stateless per-request retry orchestrator."""

    def __init__(self, decision_engine: DecisionEngine | None = None) -> None:
        self.decision_engine = decision_engine or DecisionEngine()
        # In-process confidence history per query_id (cleared on terminal states)
        self._score_history: dict[str, list[float]] = {}

    async def handle_retry(self, context: RetryRequestContextDTO) -> RetryDecisionDTO:
        """Evaluate whether to retry, applying monotonicity enforcement and backoff."""

        # Monotonicity check — if we have a prior score, current must be >= previous
        if context.last_confidence_score is not None:
            history = self._score_history.get(context.query_id, [])
            if history:
                prev_score = history[-1]
                if not self.decision_engine.is_monotonic_improvement(
                    context.last_confidence_score, prev_score
                ):
                    return RetryDecisionDTO(
                        action=RetryAction.ABORT,
                        reason_code="MONOTONIC_REGRESSION",
                        is_monotonic_regression=True,
                    )
            # Record current score in history
            history.append(context.last_confidence_score)
            self._score_history[context.query_id] = history

        # Delegate to decision engine
        decision = await self.decision_engine.decide(context)

        # Apply async sleep for backoff (non-blocking via asyncio.sleep)
        if (
            decision.action == RetryAction.RETRY_WITH_BACKOFF
            and decision.backoff_ms > 0
        ):
            await asyncio.sleep(decision.backoff_ms / 1000.0)

        # Clear history on terminal outcomes
        if decision.action == RetryAction.ABORT:
            self._score_history.pop(context.query_id, None)

        return decision

    def clear_history(self, query_id: str) -> None:
        """Explicitly clear score history for a completed or aborted query."""
        self._score_history.pop(query_id, None)
