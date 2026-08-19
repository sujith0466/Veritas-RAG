import datetime
import uuid

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

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
