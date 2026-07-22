"""Audit Log Repository Implementation.

Provides concrete SQLAlchemy queries for Audit Log entry querying and storage.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.entities.audit_log import AuditLog
from backend.repositories.base import BaseRepository
from backend.repositories.interfaces.audit_log_repository import \
    IAuditLogRepository


class AuditLogRepository(BaseRepository[AuditLog], IAuditLogRepository):
    """SQLAlchemy implementation of the AuditLog repository."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AuditLog)

    async def get_by_action(
        self, action: str, skip: int = 0, limit: int = 100
    ) -> Sequence[AuditLog]:
        """Fetch audit logs filtered by action type."""
        stmt = (
            select(AuditLog)
            .where(
                AuditLog.action == action,
                AuditLog.is_deleted.is_(False),
            )
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
            .where(
                AuditLog.user_id == user_id,
                AuditLog.is_deleted.is_(False),
            )
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
