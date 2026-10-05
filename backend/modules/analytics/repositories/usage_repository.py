import datetime
import uuid

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.analytics.models.token_usage import TokenUsageORM
from backend.modules.analytics.models.workspace_usage import WorkspaceUsage


class UsageRepository:
    """Repository for atomic workspace usage aggregation."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def get_current_period_start(dt: datetime.datetime | datetime.date | None = None) -> datetime.date:
        if dt is None:
            dt = datetime.datetime.now(datetime.timezone.utc).date()
        elif isinstance(dt, datetime.datetime):
            dt = dt.date()
        return datetime.date(dt.year, dt.month, 1)

    @staticmethod
    def get_period_end(period_start: datetime.date) -> datetime.date:
        year = period_start.year + (1 if period_start.month == 12 else 0)
        month = 1 if period_start.month == 12 else period_start.month + 1
        return datetime.date(year, month, 1)

    async def get_current_period_usage(
        self,
        workspace_id: uuid.UUID,
        period_start: datetime.date | None = None,
    ) -> WorkspaceUsage | None:
        """Fetch usage record for a workspace in the specified billing period."""
        if period_start is None:
            period_start = self.get_current_period_start()

        stmt = select(WorkspaceUsage).where(
            WorkspaceUsage.workspace_id == workspace_id,
            WorkspaceUsage.billing_period_start == period_start,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def atomic_increment(
        self,
        workspace_id: uuid.UUID,
        tokens: int,
        queries: int = 1,
        period_start: datetime.date | None = None,
    ) -> WorkspaceUsage:
        """Atomically increment used tokens and query counts using PostgreSQL ON CONFLICT UPSERT."""
        if tokens < 0 or queries < 0:
            raise ValueError("Token and query increments must be non-negative.")

        if period_start is None:
            period_start = self.get_current_period_start()

        stmt = (
            insert(WorkspaceUsage)
            .values(
                workspace_id=workspace_id,
                billing_period_start=period_start,
                used_tokens=tokens,
                used_queries=queries,
            )
            .on_conflict_do_update(
                index_elements=[WorkspaceUsage.workspace_id, WorkspaceUsage.billing_period_start],
                set_={
                    "used_tokens": WorkspaceUsage.used_tokens + tokens,
                    "used_queries": WorkspaceUsage.used_queries + queries,
                    "updated_at": func.now(),
                },
            )
            .returning(WorkspaceUsage)
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.scalar_one()

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
    ) -> tuple[TokenUsageORM, bool]:
        """Record token usage with deduplication by correlation_id to prevent double counting.

        Returns (TokenUsageORM, was_recorded_new: bool).
        """
        if prompt_tokens < 0 or completion_tokens < 0 or total_cost_usd < 0:
            raise ValueError("Token counts and cost must be non-negative.")

        # Deduplication check by correlation_id
        stmt = select(TokenUsageORM).where(TokenUsageORM.correlation_id == correlation_id)
        res = await self.session.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing is not None:
            return existing, False

        if created_at is None:
            created_at = datetime.datetime.now(datetime.timezone.utc)
        elif created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=datetime.timezone.utc)

        record = TokenUsageORM(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            user_id=user_id,
            correlation_id=correlation_id,
            provider=provider,
            model_name=model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_cost_usd=total_cost_usd,
            created_at=created_at,
        )
        self.session.add(record)
        await self.session.flush()

        tokens = prompt_tokens + completion_tokens
        period_start = self.get_current_period_start(created_at)

        # Increment durable workspace usage
        await self.atomic_increment(workspace_id, tokens, queries=1, period_start=period_start)

        # Increment user usage if user_id present
        if user_id is not None:
            from backend.modules.analytics.repositories.user_quota_repository import UserQuotaRepository
            user_repo = UserQuotaRepository(self.session)
            await user_repo.increment_user_usage(
                workspace_id=workspace_id,
                user_id=user_id,
                tokens=tokens,
                queries=1,
                period_start=period_start,
            )

        await self.session.commit()
        await self.session.refresh(record)
        return record, True

    async def get_aggregated_usage(
        self,
        workspace_id: uuid.UUID,
        period_start: datetime.date | None = None,
        period_end: datetime.date | None = None,
    ) -> dict:
        """Calculate aggregated billing period tokens from TokenUsageORM grouped by user_id and workspace_id."""
        if period_start is None:
            period_start = self.get_current_period_start()
        if period_end is None:
            period_end = self.get_period_end(period_start)

        start_dt = datetime.datetime(
            period_start.year, period_start.month, period_start.day, 0, 0, 0, tzinfo=datetime.timezone.utc
        )
        end_dt = datetime.datetime(
            period_end.year, period_end.month, period_end.day, 0, 0, 0, tzinfo=datetime.timezone.utc
        )

        # 1. Total workspace aggregate
        stmt_total = (
            select(
                func.coalesce(func.sum(TokenUsageORM.prompt_tokens), 0).label("prompt_tokens"),
                func.coalesce(func.sum(TokenUsageORM.completion_tokens), 0).label("completion_tokens"),
                func.coalesce(func.sum(TokenUsageORM.prompt_tokens + TokenUsageORM.completion_tokens), 0).label("total_tokens"),
                func.coalesce(func.sum(TokenUsageORM.total_cost_usd), 0.0).label("total_cost_usd"),
                func.count(TokenUsageORM.id).label("total_invocations"),
            )
            .where(
                TokenUsageORM.workspace_id == workspace_id,
                TokenUsageORM.created_at >= start_dt,
                TokenUsageORM.created_at < end_dt,
            )
        )
        res_total = await self.session.execute(stmt_total)
        row = res_total.one()

        # 2. Per-user breakdown
        stmt_users = (
            select(
                TokenUsageORM.user_id,
                func.coalesce(func.sum(TokenUsageORM.prompt_tokens), 0).label("prompt_tokens"),
                func.coalesce(func.sum(TokenUsageORM.completion_tokens), 0).label("completion_tokens"),
                func.coalesce(func.sum(TokenUsageORM.prompt_tokens + TokenUsageORM.completion_tokens), 0).label("total_tokens"),
                func.coalesce(func.sum(TokenUsageORM.total_cost_usd), 0.0).label("total_cost_usd"),
                func.count(TokenUsageORM.id).label("total_invocations"),
            )
            .where(
                TokenUsageORM.workspace_id == workspace_id,
                TokenUsageORM.created_at >= start_dt,
                TokenUsageORM.created_at < end_dt,
            )
            .group_by(TokenUsageORM.user_id)
        )
        res_users = await self.session.execute(stmt_users)
        user_breakdown = [
            {
                "user_id": u_row.user_id,
                "prompt_tokens": int(u_row.prompt_tokens),
                "completion_tokens": int(u_row.completion_tokens),
                "total_tokens": int(u_row.total_tokens),
                "total_cost_usd": float(u_row.total_cost_usd),
                "total_invocations": int(u_row.total_invocations),
            }
            for u_row in res_users.all()
        ]

        return {
            "workspace_id": workspace_id,
            "billing_period_start": period_start,
            "billing_period_end": period_end,
            "total_prompt_tokens": int(row.prompt_tokens),
            "total_completion_tokens": int(row.completion_tokens),
            "total_tokens": int(row.total_tokens),
            "total_cost_usd": float(row.total_cost_usd),
            "total_invocations": int(row.total_invocations),
            "user_breakdown": user_breakdown,
        }

    async def reconcile_workspace_usage(
        self,
        workspace_id: uuid.UUID,
        period_start: datetime.date | None = None,
        sync: bool = False,
    ) -> dict:
        """Reconcile token usages with durable counters and detect drift."""
        if period_start is None:
            period_start = self.get_current_period_start()

        # Get actual from TokenUsageORM
        agg = await self.get_aggregated_usage(workspace_id, period_start=period_start)

        # Get durable workspace counter
        ws_usage = await self.get_current_period_usage(workspace_id, period_start=period_start)
        durable_tokens = ws_usage.used_tokens if ws_usage else 0
        durable_queries = ws_usage.used_queries if ws_usage else 0

        drift = durable_tokens - agg["total_tokens"]
        queries_drift = durable_queries - agg["total_invocations"]
        is_consistent = (drift == 0 and queries_drift == 0)

        # User breakdown reconciliation
        from backend.modules.analytics.repositories.user_quota_repository import UserQuotaRepository
        user_repo = UserQuotaRepository(self.session)

        user_drifts = []
        for u in agg["user_breakdown"]:
            uid = u["user_id"]
            if uid:
                u_usage = await user_repo.get_user_usage(workspace_id, uid, period_start=period_start)
                u_durable_tokens = u_usage.used_tokens if u_usage else 0
                u_drift = u_durable_tokens - u["total_tokens"]
                user_drifts.append({
                    "user_id": uid,
                    "durable_tokens": u_durable_tokens,
                    "aggregated_tokens": u["total_tokens"],
                    "drift": u_drift,
                    "is_consistent": (u_drift == 0),
                })
                if sync and u_drift != 0:
                    if u_usage is not None:
                        u_usage.used_tokens = u["total_tokens"]
                        u_usage.used_queries = u["total_invocations"]
                        u_usage.updated_at = datetime.datetime.now(datetime.timezone.utc)
                    else:
                        await user_repo.increment_user_usage(
                            workspace_id, uid, u["total_tokens"], queries=u["total_invocations"], period_start=period_start
                        )

        if sync and not is_consistent:
            if ws_usage is not None:
                ws_usage.used_tokens = agg["total_tokens"]
                ws_usage.used_queries = agg["total_invocations"]
                ws_usage.updated_at = datetime.datetime.now(datetime.timezone.utc)
            else:
                await self.atomic_increment(
                    workspace_id, agg["total_tokens"], queries=agg["total_invocations"], period_start=period_start
                )
            await self.session.commit()

        return {
            "workspace_id": workspace_id,
            "billing_period_start": period_start,
            "durable_tokens": durable_tokens,
            "durable_queries": durable_queries,
            "aggregated_tokens": agg["total_tokens"],
            "aggregated_queries": agg["total_invocations"],
            "drift": drift,
            "queries_drift": queries_drift,
            "is_consistent": is_consistent,
            "synced": sync and not is_consistent,
            "user_drifts": user_drifts,
        }
