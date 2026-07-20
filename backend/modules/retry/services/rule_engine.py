"""Rule Engine — Phase 7. Maps error reasons to retry actions using priority ordering."""

from backend.modules.retry.schemas.retry_dto import (
    RetryReason, RetryAction, RetryRuleDTO,
)


class RuleEngine:
    """Evaluates which RetryAction to take for a given RetryReason."""

    def __init__(self) -> None:
        self.default_rules: list[RetryRuleDTO] = [
            RetryRuleDTO(reason=RetryReason.RATE_LIMIT,       action=RetryAction.RETRY_WITH_BACKOFF,        base_backoff_ms=1000, max_attempts_for_rule=3),
            RetryRuleDTO(reason=RetryReason.LLM_API_ERROR,    action=RetryAction.RETRY_WITH_BACKOFF,        base_backoff_ms=500,  max_attempts_for_rule=2),
            RetryRuleDTO(reason=RetryReason.LOW_CONFIDENCE,   action=RetryAction.RETRY_WITH_REWRITE,        base_backoff_ms=0,    max_attempts_for_rule=2),
            RetryRuleDTO(reason=RetryReason.TIMEOUT,          action=RetryAction.RETRY_WITH_FALLBACK_MODEL, base_backoff_ms=200,  max_attempts_for_rule=1),
            RetryRuleDTO(reason=RetryReason.MALFORMED_OUTPUT, action=RetryAction.RETRY_IMMEDIATE,           base_backoff_ms=0,    max_attempts_for_rule=1),
        ]

    def evaluate(
        self,
        reason: RetryReason,
        custom_rules: list[RetryRuleDTO] | None = None,
    ) -> RetryRuleDTO:
        """Return the highest-priority matching rule, falling back to ABORT for unknown reasons."""
        rules = custom_rules if custom_rules else self.default_rules
        for rule in rules:
            if rule.reason == reason:
                return rule
        return RetryRuleDTO(
            reason=RetryReason.UNKNOWN,
            action=RetryAction.ABORT,
            base_backoff_ms=0,
            max_attempts_for_rule=0,
        )
