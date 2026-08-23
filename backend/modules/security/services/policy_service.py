"""Policy Service for managing security policy mutations and Redis cache invalidation."""

from uuid import UUID
from structlog import get_logger
from sqlalchemy.ext.asyncio import AsyncSession

from backend.cache.client import get_redis_client
from backend.modules.security.models.policy import Policy
from backend.modules.security.repositories.policy_repository import PolicyRepository

logger = get_logger(__name__)


class PolicyService:
    """Service layer managing policy persistence and cache invalidation."""

    def __init__(self, session: AsyncSession, redis_client=None):
        self.repository = PolicyRepository(session)
        self.redis = redis_client or get_redis_client()

    async def invalidate_policy_cache(self, tenant_id: str | UUID, workspace_id: str | UUID | None = None) -> int:
        """Invalidate cached policy DTOs in Redis using safe asynchronous scan_iter."""
        t_str = str(tenant_id)
        w_str = str(workspace_id) if workspace_id else None
        deleted_count = 0

        try:
            if not self.redis:
                return 0

            if w_str:
                # Invalidate specific workspace merged cache
                ws_key = f"raguard:policy:{t_str}:{w_str}"
                deleted_count = await self.redis.delete(ws_key)
                logger.info("Invalidated workspace policy cache", tenant_id=t_str, workspace_id=w_str, key=ws_key)
            else:
                # Invalidate tenant global cache and all inherited workspace caches using scan_iter
                pattern = f"raguard:policy:{t_str}:*"
                keys_to_delete = []
                async for key in self.redis.scan_iter(match=pattern, count=100):
                    keys_to_delete.append(key)

                if keys_to_delete:
                    deleted_count = await self.redis.delete(*keys_to_delete)
                    logger.info("Invalidated tenant and child workspace policy caches", tenant_id=t_str, count=deleted_count)
        except Exception as exc:
            logger.warning("Failed to invalidate Redis policy cache; will expire via TTL", tenant_id=t_str, error=str(exc))

        return deleted_count

    async def set_policy(
        self,
        tenant_id: str | UUID,
        workspace_id: str | UUID | None = None,
        max_tokens: int | None = None,
        blocked_topics: list[str] | None = None,
        redact_pii: bool | None = None,
        block_jailbreaks: bool | None = None,
    ) -> Policy:
        """Create/update policy in DB and invalidate affected Redis cache keys."""
        policy = await self.repository.upsert_policy(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            max_tokens=max_tokens,
            blocked_topics=blocked_topics,
            redact_pii=redact_pii,
            block_jailbreaks=block_jailbreaks,
        )
        await self.invalidate_policy_cache(tenant_id, workspace_id)
        return policy

    async def delete_policy(self, tenant_id: str | UUID, workspace_id: str | UUID | None = None) -> bool:
        """Delete policy in DB and invalidate affected Redis cache keys."""
        success = await self.repository.delete_policy(tenant_id, workspace_id)
        if success:
            await self.invalidate_policy_cache(tenant_id, workspace_id)
        return success
