import structlog
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

logger = structlog.get_logger(__name__)


class PolicyEngine:
    def __init__(self):
        self.redis = get_redis_client()
        self.settings = get_settings()

    async def get_merged_policy(self, tenant_id: UUID, workspace_id: UUID) -> MergedPolicyDTO:
        if not self.settings.features.enable_ai_policy_engine:
            return MergedPolicyDTO()

        cache_key = f"raguard:policy:{tenant_id}:{workspace_id}"
        try:
            if self.redis:
                cached = await self.redis.get(cache_key)
                if cached:
                    try:
                        return MergedPolicyDTO.model_validate_json(cached)
                    except Exception:
                        await self.redis.delete(cache_key)
        except Exception as cache_exc:
            logger.warning("Redis policy cache read failed; bypassing cache", error=str(cache_exc))

        try:
            merged = await self._fetch_and_merge_from_db(str(tenant_id), str(workspace_id) if workspace_id else None)
        except Exception as db_exc:
            logger.error("Failed to load policy from database; applying safe system default", tenant_id=str(tenant_id), error=str(db_exc))
            return MergedPolicyDTO()

        try:
            if self.redis:
                await self.redis.setex(cache_key, 300, merged.model_dump_json())
        except Exception as cache_write_exc:
            logger.warning("Redis policy cache write failed", error=str(cache_write_exc))

        return merged

    async def _fetch_and_merge_from_db(self, tenant_id: str, workspace_id: str | None) -> MergedPolicyDTO:
        """Query PostgreSQL for tenant and workspace policies and merge deterministically."""
        from backend.database.engine import get_session_factory
        from backend.modules.security.repositories.policy_repository import PolicyRepository

        session_factory = get_session_factory()
        async with session_factory() as session:
            repo = PolicyRepository(session)
            tenant_policy = await repo.get_tenant_policy(tenant_id)
            workspace_policy = await repo.get_workspace_policy(tenant_id, workspace_id) if workspace_id else None

        merged = MergedPolicyDTO()

        # Apply tenant policy if configured
        if tenant_policy:
            if tenant_policy.max_tokens is not None:
                merged.max_tokens = tenant_policy.max_tokens
            if tenant_policy.blocked_topics:
                merged.blocked_topics.extend(tenant_policy.blocked_topics)
            if tenant_policy.redact_pii is not None:
                merged.redact_pii = tenant_policy.redact_pii
            if tenant_policy.block_jailbreaks is not None:
                merged.block_jailbreaks = tenant_policy.block_jailbreaks

        # Apply workspace policy overrides if configured
        if workspace_policy:
            if workspace_policy.max_tokens is not None:
                merged.max_tokens = min(merged.max_tokens, workspace_policy.max_tokens)
            if workspace_policy.blocked_topics:
                merged.blocked_topics.extend(workspace_policy.blocked_topics)
            if workspace_policy.redact_pii is not None:
                merged.redact_pii = workspace_policy.redact_pii
            if workspace_policy.block_jailbreaks is not None:
                merged.block_jailbreaks = workspace_policy.block_jailbreaks

        merged.blocked_topics = list(set(merged.blocked_topics))
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
