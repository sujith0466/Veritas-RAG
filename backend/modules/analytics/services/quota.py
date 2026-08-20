import datetime
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.cache.client import get_redis_client
from backend.database.engine import get_session_factory
from backend.modules.analytics.models.tenant_quota import TenantQuotaORM
from backend.modules.analytics.models.workspace_usage import WorkspaceUsage
from backend.modules.analytics.repositories.usage_repository import UsageRepository
from backend.modules.analytics.schemas.errors import QuotaExceededError

logger = structlog.get_logger(__name__)


class QuotaGovernor:
    """Manages workspace token quotas with PostgreSQL as durable source-of-truth and Redis cache."""

    DEFAULT_TOKEN_LIMIT = 10_000_000
    DEFAULT_BUDGET_USD = 150.0
    DEFAULT_WARNING_THRESHOLD_PCT = 0.80
    DEFAULT_IS_HARD_ENFORCED = True

    async def get_durable_usage(
        self,
        workspace_id: uuid.UUID,
        session: AsyncSession | None = None,
        period_start: datetime.date | None = None,
    ) -> int:
        """Fetch current used tokens from PostgreSQL (or Redis cache)."""
        redis = get_redis_client()
        cache_key = f"quota:usage:{workspace_id}"
        if redis:
            try:
                cached_val = await redis.get(cache_key)
                if cached_val is not None:
                    return int(cached_val)
            except Exception as e:
                logger.warning("Redis cache read failed, falling back to PostgreSQL: %s", e)

        if session is not None:
            repo = UsageRepository(session)
            usage = await repo.get_current_period_usage(workspace_id, period_start)
            used = usage.used_tokens if usage else 0
        else:
            async with get_session_factory()() as local_session:
                repo = UsageRepository(local_session)
                usage = await repo.get_current_period_usage(workspace_id, period_start)
                used = usage.used_tokens if usage else 0

        if redis:
            try:
                await redis.set(cache_key, used, ex=60)
            except Exception:
                pass

        return used

    async def get_quota_settings(
        self,
        workspace_id: uuid.UUID | None = None,
        tenant_id: str | None = None,
        session: AsyncSession | None = None,
    ) -> TenantQuotaORM:
        """Fetch quota configuration for a workspace or legacy tenant_id."""
        async def _query(s: AsyncSession) -> TenantQuotaORM | None:
            if workspace_id:
                stmt = select(TenantQuotaORM).where(TenantQuotaORM.workspace_id == workspace_id)
                res = await s.execute(stmt)
                item = res.scalar_one_or_none()
                if item:
                    return item

            if tenant_id:
                stmt = select(TenantQuotaORM).where(TenantQuotaORM.tenant_id == tenant_id)
                res = await s.execute(stmt)
                item = res.scalar_one_or_none()
                if item:
                    return item

            return None

        if session is not None:
            quota = await _query(session)
        else:
            async with get_session_factory()() as local_session:
                quota = await _query(local_session)

        if quota:
            return quota

        # Return default quota specification if not customized in DB
        return TenantQuotaORM(
            tenant_id=tenant_id or (str(workspace_id) if workspace_id else "default"),
            workspace_id=workspace_id,
            monthly_token_limit=self.DEFAULT_TOKEN_LIMIT,
            monthly_budget_usd=self.DEFAULT_BUDGET_USD,
            warning_threshold_pct=self.DEFAULT_WARNING_THRESHOLD_PCT,
            is_hard_enforced=self.DEFAULT_IS_HARD_ENFORCED,
        )

    async def check_quota(
        self,
        workspace_id: uuid.UUID,
        tenant_id: str | None = None,
        session: AsyncSession | None = None,
    ) -> tuple[bool, int, int, bool]:
        """Check if workspace quota is exceeded.

        Returns: (is_exceeded, used_tokens, monthly_token_limit, is_hard_enforced)
        """
        quota_settings = await self.get_quota_settings(workspace_id, tenant_id, session)
        used_tokens = await self.get_durable_usage(workspace_id, session)

        limit = quota_settings.monthly_token_limit
        is_hard = quota_settings.is_hard_enforced
        is_exceeded = bool(is_hard and (used_tokens >= limit))

        return is_exceeded, used_tokens, limit, is_hard

    async def record_usage(
        self,
        workspace_id: uuid.UUID,
        tokens: int,
        queries: int = 1,
        session: AsyncSession | None = None,
        period_start: datetime.date | None = None,
    ) -> WorkspaceUsage:
        """Atomically record used tokens and query counts in PostgreSQL."""
        if tokens < 0 or queries < 0:
            raise ValueError("Token and query increments must be non-negative.")

        if session is not None:
            repo = UsageRepository(session)
            usage = await repo.atomic_increment(workspace_id, tokens, queries, period_start)
        else:
            async with get_session_factory()() as local_session:
                repo = UsageRepository(local_session)
                usage = await repo.atomic_increment(workspace_id, tokens, queries, period_start)

        redis = get_redis_client()
        if redis:
            try:
                cache_key = f"quota:usage:{workspace_id}"
                await redis.set(cache_key, usage.used_tokens, ex=60)
            except Exception as e:
                logger.warning("Failed updating Redis usage cache: %s", e)

        return usage

    # --- Backward compatibility methods ---

    async def get_remaining_tokens(self, tenant_id: str) -> int:
        """Fetch remaining tokens with PostgreSQL fallback (fail-safe)."""
        redis = get_redis_client()
        key = f"quota:tokens:{tenant_id}"
        if redis:
            try:
                current = await redis.get(key)
                if current is not None:
                    return int(current)
            except Exception:
                pass

        # Fallback to DB
        quota = await self.get_quota_settings(tenant_id=tenant_id)
        # Attempt UUID parsing if tenant_id is formatted as UUID
        ws_id = None
        try:
            ws_id = uuid.UUID(tenant_id)
        except Exception:
            pass

        used = await self.get_durable_usage(ws_id) if ws_id else 0
        remaining = max(0, quota.monthly_token_limit - used)

        if redis:
            try:
                await redis.set(key, remaining, ex=60)
            except Exception:
                pass

        return remaining

    async def set_remaining_tokens(self, tenant_id: str, tokens: int) -> None:
        """Set the absolute remaining token limit in cache."""
        redis = get_redis_client()
        if redis:
            try:
                key = f"quota:tokens:{tenant_id}"
                await redis.set(key, tokens, ex=3600)
            except Exception:
                pass

    async def check_and_reserve(self, tenant_id: str, est_tokens: int) -> bool:
        """Pre-check quota allowance."""
        remaining = await self.get_remaining_tokens(tenant_id)
        if remaining < est_tokens:
            raise QuotaExceededError(f"Quota exhausted for tenant {tenant_id}")
        return True

    async def adjust_reservation_diff(self, tenant_id: str, diff_tokens: int):
        """Refund or subtract tokens from cache."""
        redis = get_redis_client()
        if redis:
            try:
                key = f"quota:tokens:{tenant_id}"
                await redis.incrby(key, diff_tokens)
            except Exception:
                pass
