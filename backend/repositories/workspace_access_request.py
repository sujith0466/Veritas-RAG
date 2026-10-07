"""Workspace Access Request Repository.

Handles persistence, lookup, row locking, and status transitions for WorkspaceAccessRequest entities.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models.entities.workspace_access_request import (
    AccessRequestStatus,
    WorkspaceAccessRequest,
)
from backend.repositories.base import BaseRepository


class WorkspaceAccessRequestRepository(BaseRepository[WorkspaceAccessRequest]):
    """Repository for managing WorkspaceAccessRequest entities."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, WorkspaceAccessRequest)

    async def get_by_id(
        self, request_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> WorkspaceAccessRequest | None:
        """Fetch an access request by ID enforcing workspace tenant isolation."""
        stmt = (
            select(self.model_class)
            .options(
                selectinload(self.model_class.user),
                selectinload(self.model_class.reviewed_by),
            )
            .where(
                self.model_class.id == request_id,
                self.model_class.workspace_id == workspace_id,
                self.model_class.is_deleted == False,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_id_for_update(
        self, request_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> WorkspaceAccessRequest | None:
        """Fetch an access request by ID under pessimistic row lock (SELECT ... FOR UPDATE)."""
        stmt = (
            select(self.model_class)
            .options(
                selectinload(self.model_class.user),
                selectinload(self.model_class.reviewed_by),
            )
            .where(
                self.model_class.id == request_id,
                self.model_class.workspace_id == workspace_id,
                self.model_class.is_deleted == False,
            )
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_active_pending(
        self, workspace_id: uuid.UUID, user_id: uuid.UUID, request_type: str
    ) -> WorkspaceAccessRequest | None:
        """Check for existing pending request of the same type for user in workspace."""
        stmt = select(self.model_class).where(
            self.model_class.workspace_id == workspace_id,
            self.model_class.user_id == user_id,
            self.model_class.request_type == request_type,
            self.model_class.status == AccessRequestStatus.PENDING.value,
            self.model_class.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_workspace(
        self,
        workspace_id: uuid.UUID,
        status: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[WorkspaceAccessRequest], int]:
        """Paginated list of access requests for a workspace with total count."""
        base_filters = [
            self.model_class.workspace_id == workspace_id,
            self.model_class.is_deleted == False,
        ]
        if status:
            base_filters.append(self.model_class.status == status.upper())

        # Count total
        count_stmt = select(func.count(self.model_class.id)).where(*base_filters)
        count_res = await self.session.execute(count_stmt)
        total = count_res.scalar() or 0

        # Fetch items
        stmt = (
            select(self.model_class)
            .options(
                selectinload(self.model_class.user),
                selectinload(self.model_class.reviewed_by),
            )
            .where(*base_filters)
            .order_by(self.model_class.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())

        return items, total

    async def count_pending_in_workspace(self, workspace_id: uuid.UUID) -> int:
        """Count total active pending access requests in a workspace."""
        stmt = select(func.count(self.model_class.id)).where(
            self.model_class.workspace_id == workspace_id,
            self.model_class.status == AccessRequestStatus.PENDING.value,
            self.model_class.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0
