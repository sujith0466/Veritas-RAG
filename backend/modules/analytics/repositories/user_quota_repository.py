"""Repository for workspace user-level quotas and per-user usage tracking."""

import datetime
from datetime import UTC
import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.analytics.models.workspace_user_quota import WorkspaceUserQuotaORM
from backend.modules.analytics.models.workspace_user_usage import WorkspaceUserUsage


class UserQuotaRepository:
    """Repository handling database operations for user-level quotas and usage."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_quota(
        self, workspace_id: uuid.UUID, user_id: uuid.UUID
    ) -> WorkspaceUserQuotaORM | None:
        """Fetch user quota configuration within a workspace."""
        stmt = select(WorkspaceUserQuotaORM).where(
            WorkspaceUserQuotaORM.workspace_id == workspace_id,
            WorkspaceUserQuotaORM.user_id == user_id,
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def set_user_quota(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        monthly_token_budget: int | None,
        is_hard_enforced: bool = True,
        warning_threshold_pct: float = 0.80,
    ) -> WorkspaceUserQuotaORM:
        """Upsert a user quota configuration within a workspace."""
        stmt = (
            insert(WorkspaceUserQuotaORM)
            .values(
                id=uuid.uuid4(),
                workspace_id=workspace_id,
                user_id=user_id,
                monthly_token_budget=monthly_token_budget,
                is_hard_enforced=is_hard_enforced,
                warning_threshold_pct=warning_threshold_pct,
            )
            .on_conflict_do_update(
                index_elements=["workspace_id", "user_id"],
                set_={
                    "monthly_token_budget": monthly_token_budget,
                    "is_hard_enforced": is_hard_enforced,
                    "warning_threshold_pct": warning_threshold_pct,
                    "updated_at": datetime.datetime.now(UTC),
                },
            )
            .returning(WorkspaceUserQuotaORM)
        )
        res = await self.session.execute(stmt)
        obj = res.scalar_one()
        await self.session.commit()
        await self.session.refresh(obj)
        return obj

    async def list_user_quotas(
        self, workspace_id: uuid.UUID
    ) -> list[WorkspaceUserQuotaORM]:
        """List all configured user quotas for a workspace."""
        stmt = select(WorkspaceUserQuotaORM).where(
            WorkspaceUserQuotaORM.workspace_id == workspace_id
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_user_usage(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        period_start: datetime.date | None = None,
    ) -> WorkspaceUserUsage | None:
        """Fetch durable aggregate token and query consumption for a user in the billing period."""
        if period_start is None:
            today = datetime.datetime.now(UTC).date()
            period_start = today.replace(day=1)

        stmt = select(WorkspaceUserUsage).where(
            WorkspaceUserUsage.workspace_id == workspace_id,
            WorkspaceUserUsage.user_id == user_id,
            WorkspaceUserUsage.billing_period_start == period_start,
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def increment_user_usage(
        self,
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        tokens: int,
        queries: int = 1,
        period_start: datetime.date | None = None,
    ) -> WorkspaceUserUsage:
        """Atomically increment durable used tokens and queries for a user in PostgreSQL."""
        if period_start is None:
            today = datetime.datetime.now(UTC).date()
            period_start = today.replace(day=1)

        stmt = (
            insert(WorkspaceUserUsage)
            .values(
                workspace_id=workspace_id,
                user_id=user_id,
                billing_period_start=period_start,
                used_tokens=tokens,
                used_queries=queries,
            )
            .on_conflict_do_update(
                index_elements=["workspace_id", "user_id", "billing_period_start"],
                set_={
                    "used_tokens": WorkspaceUserUsage.used_tokens + tokens,
                    "used_queries": WorkspaceUserUsage.used_queries + queries,
                    "updated_at": datetime.datetime.now(UTC),
                },
            )
            .returning(WorkspaceUserUsage)
        )
        res = await self.session.execute(stmt)
        obj = res.scalar_one()
        await self.session.commit()
        await self.session.refresh(obj)
        return obj
