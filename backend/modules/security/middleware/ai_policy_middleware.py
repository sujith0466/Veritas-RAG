from uuid import UUID

from backend.cache.client import get_redis_client
from backend.core.config import get_settings
from backend.modules.generation.services.prompt_guard import PromptGuard
from backend.modules.security.middleware.evaluators import (
    BlockedTopicEvaluator,
    PIIRedactionEvaluator,
    PromptInjectionEvaluator,
    TokenLimitEvaluator,
)
from backend.modules.security.schemas.policy_dto import (
    MergedPolicyDTO,
    TenantPolicyDTO,
    WorkspacePolicyDTO,
)
from backend.modules.security.services.dlp import DLPEngine


class PolicyEngine:
    def __init__(self):
        self.redis = get_redis_client()
        self.settings = get_settings()

    async def get_merged_policy(self, tenant_id: UUID, workspace_id: UUID) -> MergedPolicyDTO:
        if not self.settings.features.enable_ai_policy_engine:
            return MergedPolicyDTO()

        cache_key = f"raguard:policy:{tenant_id}:{workspace_id}"
        cached = await self.redis.get(cache_key)
        if cached:
            return MergedPolicyDTO.model_validate_json(cached)

        # Fallback to defaults (in a real scenario, this fetches from DB)
        # Mocking DB fetch for deterministic architecture requirement:
        # Tenant overrides system default, workspace overrides tenant.
        tenant_policy = TenantPolicyDTO(
            max_tokens=2048,
            blocked_topics=["financial advice", "medical diagnosis"],
            redact_pii=True,
            block_jailbreaks=True
        )
        workspace_policy = WorkspacePolicyDTO(
            max_tokens=1024, # Stricter
            blocked_topics=[],
            redact_pii=None,
            block_jailbreaks=None
        )

        merged = MergedPolicyDTO()
        # Apply tenant
        if tenant_policy.max_tokens is not None:
            merged.max_tokens = tenant_policy.max_tokens
        if tenant_policy.blocked_topics:
            merged.blocked_topics.extend(tenant_policy.blocked_topics)
        if tenant_policy.redact_pii is not None:
            merged.redact_pii = tenant_policy.redact_pii
        if tenant_policy.block_jailbreaks is not None:
            merged.block_jailbreaks = tenant_policy.block_jailbreaks

        # Apply workspace overrides
        if workspace_policy.max_tokens is not None:
            merged.max_tokens = min(merged.max_tokens, workspace_policy.max_tokens)
        if workspace_policy.blocked_topics:
            merged.blocked_topics.extend(workspace_policy.blocked_topics)
        if workspace_policy.redact_pii is not None:
            merged.redact_pii = workspace_policy.redact_pii
        if workspace_policy.block_jailbreaks is not None:
            merged.block_jailbreaks = workspace_policy.block_jailbreaks

        merged.blocked_topics = list(set(merged.blocked_topics))

        # Cache with 5 min TTL
        await self.redis.setex(cache_key, 300, merged.model_dump_json())
        return merged

class AIPolicyMiddleware:
    def __init__(self):
        self.policy_engine = PolicyEngine()
        self.token_evaluator = TokenLimitEvaluator()
        self.prompt_evaluator = PromptInjectionEvaluator(PromptGuard())
        self.topic_evaluator = BlockedTopicEvaluator()
        self.pii_evaluator = PIIRedactionEvaluator(DLPEngine())

    async def evaluate_request(self, tenant_id: UUID, workspace_id: UUID, query: str) -> str:
        policy = await self.policy_engine.get_merged_policy(tenant_id, workspace_id)

        self.token_evaluator.evaluate(query, policy)
        self.prompt_evaluator.evaluate(query, policy)
        self.topic_evaluator.evaluate(query, policy)

        return self.pii_evaluator.evaluate(query, policy)
