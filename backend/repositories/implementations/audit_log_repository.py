"""Audit Log Repository Implementation.

Provides concrete SQLAlchemy queries for Audit Log entry querying and storage.
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Any
import uuid

from sqlalchemy import String, and_, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.entities.audit_log import AuditLog
from backend.repositories.base import ImmutableBaseRepository
from backend.repositories.interfaces.audit_log_repository import IAuditLogRepository


class AuditLogRepository(ImmutableBaseRepository[AuditLog], IAuditLogRepository):
    """SQLAlchemy implementation of the immutable AuditLog repository."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AuditLog)

    async def get_by_action(
        self, action: str, skip: int = 0, limit: int = 100
    ) -> Sequence[AuditLog]:
        """Fetch audit logs filtered by action type."""
        stmt = (
            select(AuditLog)
            .where(AuditLog.action == action)
            .order_by(AuditLog.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_user_id(
        self, user_id: uuid.UUID, skip: int = 0, limit: int = 100
    ) -> Sequence[AuditLog]:
        """Fetch audit logs associated with a specific user."""
        stmt = (
            select(AuditLog)
            .where(AuditLog.user_id == user_id)
            .order_by(AuditLog.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_tenant_id(
        self, tenant_id: uuid.UUID, skip: int = 0, limit: int = 100
    ) -> Sequence[AuditLog]:
        """Fetch audit logs scoped to a specific workspace/tenant."""
        stmt = (
            select(AuditLog)
            .where(AuditLog.tenant_id == tenant_id)
            .order_by(AuditLog.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def search_logs(
        self,
        tenant_id: uuid.UUID,
        query: str | None = None,
        action: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[AuditLog], int]:
        """Search and filter audit logs with true count pagination."""
        filters = [AuditLog.tenant_id == tenant_id]

        if action and action.strip():
            filters.append(AuditLog.action == action.strip())

        if start_date:
            filters.append(AuditLog.created_at >= start_date)

        if end_date:
            filters.append(AuditLog.created_at <= end_date)

        if query and query.strip():
            q = f"%{query.strip()}%"
            query_filter = or_(
                AuditLog.action.ilike(q),
                AuditLog.resource_type.ilike(q),
                AuditLog.resource_id.ilike(q),
                cast(AuditLog.user_id, String).ilike(q),
            )
            filters.append(query_filter)

        count_stmt = select(func.count(AuditLog.id)).where(and_(*filters))
        count_res = await self.session.execute(count_stmt)
        total_count = count_res.scalar_one() or 0

        data_stmt = (
            select(AuditLog)
            .where(and_(*filters))
            .order_by(AuditLog.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        data_res = await self.session.execute(data_stmt)
        items = data_res.scalars().all()

        return items, total_count
