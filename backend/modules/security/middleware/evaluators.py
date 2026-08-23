from backend.core.exceptions import ApplicationException
from backend.modules.generation.services.prompt_guard import PromptGuard
from backend.modules.security.schemas.policy_dto import MergedPolicyDTO
from backend.modules.security.services.dlp import DLPEngine
from backend.observability.metrics.prometheus import (
    record_blocked_prompt,
    record_pii_redaction,
    record_policy_violation,
    record_prompt_injection,
)


class PolicyViolationError(ApplicationException):
    http_status: int = 403
    error_code: str = "POL_001"

    def __init__(self, message: str, violation_type: str = "general"):
        self.violation_type = violation_type
        super().__init__(message=message, detail={"violation_type": violation_type}, error_code="POL_001")

class TokenLimitEvaluator:
    def evaluate(self, query: str, policy: MergedPolicyDTO) -> None:
        # A simple estimation: 1 word ~ 1.3 tokens
        estimated_tokens = int(len(query.split()) * 1.3)
        if estimated_tokens > policy.max_tokens:
            record_policy_violation("token_limit_exceeded")
            raise PolicyViolationError(
                f"Query exceeds maximum allowed tokens ({policy.max_tokens}).",
                violation_type="token_limit_exceeded"
            )

class PromptInjectionEvaluator:
    def __init__(self, prompt_guard: PromptGuard):
        self.prompt_guard = prompt_guard

    def evaluate(self, query: str, policy: MergedPolicyDTO) -> None:
        if not policy.block_jailbreaks:
            return

        # We reuse prompt_guard.scan_for_injection
        if self.prompt_guard.scan_for_injection(query):
            record_prompt_injection()
            record_policy_violation("prompt_injection")
            raise PolicyViolationError(
                "Prompt injection or jailbreak attempt detected.",
                violation_type="prompt_injection"
            )

class BlockedTopicEvaluator:
    def evaluate(self, query: str, policy: MergedPolicyDTO) -> None:
        if not policy.blocked_topics:
            return

        # In a real implementation, this would call an LLM with use_lite_model=True
        # For this deterministic implementation, we use simple string matching
        query_lower = query.lower()
        for topic in policy.blocked_topics:
            if topic.lower() in query_lower:
                record_blocked_prompt(topic)
                record_policy_violation("blocked_topic")
                raise PolicyViolationError(
                    f"Query contains restricted topic: {topic}",
                    violation_type="blocked_topic"
                )

class PIIRedactionEvaluator:
    def __init__(self, dlp_engine: DLPEngine):
        self.dlp_engine = dlp_engine

    def evaluate(self, query: str, policy: MergedPolicyDTO) -> str:
        if not policy.redact_pii:
            return query

        result = self.dlp_engine.redact(query)
        if result.entities_redacted > 0:
            for _ in range(result.entities_redacted):
                record_pii_redaction()
        return result.redacted_text
