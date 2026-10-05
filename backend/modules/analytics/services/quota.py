from dataclasses import dataclass
import datetime
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.cache.client import get_redis_client
from backend.database.engine import get_session_factory
from backend.modules.analytics.models.tenant_quota import TenantQuotaORM
from backend.modules.analytics.models.token_usage import TokenUsageORM
from backend.modules.analytics.models.workspace_usage import WorkspaceUsage
from backend.modules.analytics.repositories.usage_repository import UsageRepository
from backend.modules.analytics.schemas.errors import QuotaExceededError

logger = structlog.get_logger(__name__)


@dataclass
class HierarchicalQuotaCheckResult:
    """Result of hierarchical quota verification (workspace and user level)."""

    is_allowed: bool
    blocked_by: str | None = None  # None, 'user_quota', 'workspace_quota'
    user_used_tokens: int = 0
    user_token_limit: int | None = None
    workspace_used_tokens: int = 0
    workspace_token_limit: int = 0
    detail: str | None = None


class QuotaGovernor:
    """Manages workspace and user token quotas with PostgreSQL as durable source-of-truth and Redis cache."""

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

    async def get_user_durable_usage(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        session: AsyncSession | None = None,
        period_start: datetime.date | None = None,
    ) -> int:
        """Fetch current used tokens for a specific user from PostgreSQL (or Redis cache)."""
        redis = get_redis_client()
        cache_key = f"quota:usage:{workspace_id}:user:{user_id}"
        if redis:
            try:
                cached_val = await redis.get(cache_key)
                if cached_val is not None:
                    return int(cached_val)
            except Exception as e:
                logger.warning("Redis user cache read failed: %s", e)

        from backend.modules.analytics.repositories.user_quota_repository import UserQuotaRepository

        if session is not None:
            repo = UserQuotaRepository(session)
            u_usage = await repo.get_user_usage(workspace_id, user_id, period_start)
            used = u_usage.used_tokens if u_usage else 0
        else:
            async with get_session_factory()() as local_session:
                repo = UserQuotaRepository(local_session)
                u_usage = await repo.get_user_usage(workspace_id, user_id, period_start)
                used = u_usage.used_tokens if u_usage else 0

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

            # Fallback to workspace_settings canonical limits if tenant_quotas has no record
            target_wid = workspace_id
            if target_wid is None and tenant_id:
                try:
                    target_wid = uuid.UUID(tenant_id)
                except (ValueError, TypeError):
                    pass

            if target_wid:
                from backend.models.entities.workspace_settings import WorkspaceSettings
                stmt_ws = select(WorkspaceSettings).where(WorkspaceSettings.workspace_id == target_wid)
                res_ws = await s.execute(stmt_ws)
                ws_settings = res_ws.scalar_one_or_none()
                if ws_settings and ws_settings.settings_json and "limits" in ws_settings.settings_json:
                    limits = ws_settings.settings_json.get("limits") or {}
                    tb = limits.get("monthly_token_budget")
                    if tb is not None and int(tb) > 0:
                        return TenantQuotaORM(
                            tenant_id=tenant_id or str(target_wid),
                            workspace_id=target_wid,
                            monthly_token_limit=int(tb),
                            monthly_budget_usd=self.DEFAULT_BUDGET_USD,
                            warning_threshold_pct=self.DEFAULT_WARNING_THRESHOLD_PCT,
                            is_hard_enforced=self.DEFAULT_IS_HARD_ENFORCED,
                        )

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

    async def check_hierarchical_quota(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
        requested_tokens: int = 0,
        session: AsyncSession | None = None,
    ) -> HierarchicalQuotaCheckResult:
        """Evaluate hierarchical quota: Workspace Quota AND User Quota."""
        # 1. Evaluate Workspace Quota
        ws_quota = await self.get_quota_settings(workspace_id=workspace_id, session=session)
        ws_used = await self.get_durable_usage(workspace_id, session)

        if ws_quota.is_hard_enforced and (ws_used + requested_tokens > ws_quota.monthly_token_limit):
            return HierarchicalQuotaCheckResult(
                is_allowed=False,
                blocked_by="workspace_quota",
                user_used_tokens=0,
                user_token_limit=None,
                workspace_used_tokens=ws_used,
                workspace_token_limit=ws_quota.monthly_token_limit,
                detail=f"Workspace token budget exhausted ({ws_used}/{ws_quota.monthly_token_limit}).",
            )

        # 2. Evaluate User Quota if user_id is provided
        user_used = 0
        user_limit = None
        if user_id is not None:
            from backend.modules.analytics.repositories.user_quota_repository import UserQuotaRepository
            if session is not None:
                repo = UserQuotaRepository(session)
                u_quota = await repo.get_user_quota(workspace_id, user_id)
            else:
                async with get_session_factory()() as local_session:
                    repo = UserQuotaRepository(local_session)
                    u_quota = await repo.get_user_quota(workspace_id, user_id)

            if u_quota and u_quota.monthly_token_budget is not None:
                user_limit = u_quota.monthly_token_budget
                user_used = await self.get_user_durable_usage(workspace_id, user_id, session)
                if u_quota.is_hard_enforced and (user_used + requested_tokens > user_limit):
                    return HierarchicalQuotaCheckResult(
                        is_allowed=False,
                        blocked_by="user_quota",
                        user_used_tokens=user_used,
                        user_token_limit=user_limit,
                        workspace_used_tokens=ws_used,
                        workspace_token_limit=ws_quota.monthly_token_limit,
                        detail=f"User monthly token budget exhausted ({user_used}/{user_limit}).",
                    )

        return HierarchicalQuotaCheckResult(
            is_allowed=True,
            blocked_by=None,
            user_used_tokens=user_used,
            user_token_limit=user_limit,
            workspace_used_tokens=ws_used,
            workspace_token_limit=ws_quota.monthly_token_limit,
            detail=None,
        )

    async def enforce_hierarchical_quota(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
        requested_tokens: int = 0,
        session: AsyncSession | None = None,
    ) -> HierarchicalQuotaCheckResult:
        """Enforces hierarchical quota, raising QuotaExceededError if blocked."""
        result = await self.check_hierarchical_quota(
            workspace_id=workspace_id,
            user_id=user_id,
            requested_tokens=requested_tokens,
            session=session,
        )
        if not result.is_allowed:
            raise QuotaExceededError(result.detail or "Quota exceeded")
        return result

    async def record_usage(
        self,
        workspace_id: uuid.UUID,
        tokens: int,
        queries: int = 1,
        user_id: uuid.UUID | None = None,
        session: AsyncSession | None = None,
        period_start: datetime.date | None = None,
    ) -> WorkspaceUsage:
        """Atomically record used tokens and query counts in PostgreSQL for workspace and user."""
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

        # Track per-user usage attribution if user_id is provided
        if user_id is not None:
            from backend.modules.analytics.repositories.user_quota_repository import UserQuotaRepository
            if session is not None:
                u_repo = UserQuotaRepository(session)
                u_res = await u_repo.increment_user_usage(workspace_id, user_id, tokens, queries, period_start)
            else:
                async with get_session_factory()() as local_session:
                    u_repo = UserQuotaRepository(local_session)
                    u_res = await u_repo.increment_user_usage(workspace_id, user_id, tokens, queries, period_start)

            if redis:
                try:
                    u_cache_key = f"quota:usage:{workspace_id}:user:{user_id}"
                    await redis.set(u_cache_key, u_res.used_tokens, ex=60)
                except Exception:
                    pass

        return usage

    async def record_token_usage(
        self,
        workspace_id: uuid.UUID,
        tenant_id: str,
        prompt_tokens: int,
        completion_tokens: int,
        correlation_id: str,
        provider: str = "default",
        model_name: str = "default",
        total_cost_usd: float = 0.0,
        user_id: uuid.UUID | None = None,
        created_at: datetime.datetime | None = None,
        session: AsyncSession | None = None,
    ) -> tuple[TokenUsageORM, bool]:
        """Record detailed token usage with correlation_id deduplication and durable counter updates."""
        if session is not None:
            repo = UsageRepository(session)
            return await repo.record_token_usage(
                workspace_id=workspace_id,
                tenant_id=tenant_id,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                correlation_id=correlation_id,
                provider=provider,
                model_name=model_name,
                total_cost_usd=total_cost_usd,
                user_id=user_id,
                created_at=created_at,
            )
        else:
            async with get_session_factory()() as local_session:
                repo = UsageRepository(local_session)
                return await repo.record_token_usage(
                    workspace_id=workspace_id,
                    tenant_id=tenant_id,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    correlation_id=correlation_id,
                    provider=provider,
                    model_name=model_name,
                    total_cost_usd=total_cost_usd,
                    user_id=user_id,
                    created_at=created_at,
                )

    async def get_aggregated_usage(
        self,
        workspace_id: uuid.UUID,
        period_start: datetime.date | None = None,
        period_end: datetime.date | None = None,
        session: AsyncSession | None = None,
    ) -> dict:
        """Fetch aggregated usage grouped by workspace and user for a billing period."""
        if session is not None:
            repo = UsageRepository(session)
            return await repo.get_aggregated_usage(workspace_id, period_start, period_end)
        else:
            async with get_session_factory()() as local_session:
                repo = UsageRepository(local_session)
                return await repo.get_aggregated_usage(workspace_id, period_start, period_end)

    async def reconcile_usage(
        self,
        workspace_id: uuid.UUID,
        period_start: datetime.date | None = None,
        sync: bool = False,
        session: AsyncSession | None = None,
    ) -> dict:
        """Reconcile token usages with durable counters and report/correct drift."""
        if session is not None:
            repo = UsageRepository(session)
            return await repo.reconcile_workspace_usage(workspace_id, period_start, sync)
        else:
            async with get_session_factory()() as local_session:
                repo = UsageRepository(local_session)
                return await repo.reconcile_workspace_usage(workspace_id, period_start, sync)

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
