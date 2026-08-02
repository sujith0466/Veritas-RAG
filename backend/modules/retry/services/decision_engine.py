"""Decision Engine — Phase 7. Combines policy, budget, rules, and monotonicity into a decision."""

from backend.modules.retry.schemas.retry_dto import (
    RetryAction,
    RetryDecisionDTO,
    RetryRequestContextDTO,
)
from backend.modules.retry.services.budget_manager import RetryBudgetManager
from backend.modules.retry.services.policy_engine import PolicyEngine
from backend.modules.retry.services.rule_engine import RuleEngine


class DecisionEngine:
    """Aggregates policy, budget, rule evaluation and returns a deterministic RetryDecisionDTO."""

    def __init__(
        self,
        rule_engine: RuleEngine | None = None,
        budget_manager: RetryBudgetManager | None = None,
        policy_engine: PolicyEngine | None = None,
    ) -> None:
        self.rule_engine = rule_engine or RuleEngine()
        self.budget_manager = budget_manager or RetryBudgetManager()
        self.policy_engine = policy_engine or PolicyEngine()

    async def decide(self, context: RetryRequestContextDTO) -> RetryDecisionDTO:
        """Return a RetryDecisionDTO for the given context."""

        # 1. Hard budget check (attempt > 3 is always rejected)
        has_budget = await self.budget_manager.check_budget(
            context.tenant_id, context.query_id, context.attempt_number
        )
        if not has_budget:
            return RetryDecisionDTO(
                action=RetryAction.ABORT,
                reason_code="BUDGET_EXHAUSTED",
                is_budget_exhausted=True,
            )

        # 2. Policy check
        policy = await self.policy_engine.get_policy(context.tenant_id)
        if context.attempt_number > policy.max_total_retries:
            return RetryDecisionDTO(
                action=RetryAction.ABORT,
                reason_code="POLICY_LIMIT_REACHED",
                is_budget_exhausted=True,
            )

        # 3. Rule evaluation with custom rules first, then defaults
        rule = self.rule_engine.evaluate(context.reason, policy.rules or None)
        if rule.action == RetryAction.ABORT:
            return RetryDecisionDTO(
                action=RetryAction.ABORT,
                reason_code="NO_MATCHING_RULE_OR_ABORT",
            )

        # 4. Exponential backoff: base_backoff_ms * 2^(attempt-1)
        backoff_ms = rule.base_backoff_ms * (2 ** (context.attempt_number - 1))

        return RetryDecisionDTO(
            action=rule.action,
            backoff_ms=backoff_ms,
            reason_code="RULE_MATCHED",
        )

    def is_monotonic_improvement(
        self, current_score: float, previous_score: float
    ) -> bool:
        """Return True if current_score >= previous_score (monotonic improvement)."""
        return current_score >= previous_score
