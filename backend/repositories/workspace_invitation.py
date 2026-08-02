"""Workspace Invitation Repository.

Handles persistence, lookup, row locking, and batch expiration for WorkspaceInvitation entities.
"""

import datetime
import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models.entities.workspace_invitation import (
    InvitationStatus,
    WorkspaceInvitation,
)
from backend.repositories.base import BaseRepository


class WorkspaceInvitationRepository(BaseRepository[WorkspaceInvitation]):
    """Repository for managing WorkspaceInvitation entities."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, WorkspaceInvitation)

    async def get_by_id(
        self, invitation_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> WorkspaceInvitation | None:
        """Fetch an invitation by ID, strictly enforcing workspace tenant isolation."""
        stmt = (
            select(self.model_class)
            .options(
                selectinload(self.model_class.workspace),
                selectinload(self.model_class.invited_by),
                selectinload(self.model_class.revoked_by),
            )
            .where(
                self.model_class.id == invitation_id,
                self.model_class.workspace_id == workspace_id,
                self.model_class.is_deleted == False,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_token_hash(self, token_hash: str) -> WorkspaceInvitation | None:
        """Fetch an invitation by its SHA-256 token hash for verification/acceptance."""
        stmt = (
            select(self.model_class)
            .options(
                selectinload(self.model_class.workspace),
                selectinload(self.model_class.invited_by),
            )
            .where(
                self.model_class.token_hash == token_hash,
                self.model_class.is_deleted == False,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_token_hash_for_update(self, token_hash: str) -> WorkspaceInvitation | None:
        """Fetch an invitation by its SHA-256 token hash with row-level lock (SELECT FOR UPDATE)."""
        stmt = (
            select(self.model_class)
            .options(
                selectinload(self.model_class.workspace),
                selectinload(self.model_class.invited_by),
            )
            .where(
                self.model_class.token_hash == token_hash,
                self.model_class.is_deleted == False,
            )
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_pending_by_workspace_and_email(
        self, workspace_id: uuid.UUID, email: str
    ) -> WorkspaceInvitation | None:
        """Check for existing pending invitation for a normalized email in a workspace."""
        stmt = select(self.model_class).where(
            self.model_class.workspace_id == workspace_id,
            func.lower(self.model_class.email) == email.strip().lower(),
            self.model_class.status == InvitationStatus.PENDING.value,
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
    ) -> tuple[list[WorkspaceInvitation], int]:
        """Paginated list of invitations for a workspace with total count."""
        base_filters = [
            self.model_class.workspace_id == workspace_id,
            self.model_class.is_deleted == False,
        ]
        if status:
            base_filters.append(self.model_class.status == status)

        # Count total
        count_stmt = select(func.count(self.model_class.id)).where(*base_filters)
        count_res = await self.session.execute(count_stmt)
        total = count_res.scalar() or 0

        # Fetch items
        stmt = (
            select(self.model_class)
            .options(
                selectinload(self.model_class.invited_by),
                selectinload(self.model_class.revoked_by),
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
        """Count total active pending invitations in a workspace."""
        stmt = select(func.count(self.model_class.id)).where(
            self.model_class.workspace_id == workspace_id,
            self.model_class.status == InvitationStatus.PENDING.value,
            self.model_class.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def find_expired_pending(
        self, before_timestamp: datetime.datetime
    ) -> list[WorkspaceInvitation]:
        """Find all PENDING invitations that have expired before the given timestamp."""
        stmt = (
            select(self.model_class)
            .where(
                self.model_class.status == InvitationStatus.PENDING.value,
                self.model_class.expires_at < before_timestamp,
                self.model_class.is_deleted == False,
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def batch_expire(
        self, invitation_ids: list[uuid.UUID], updated_at: datetime.datetime
    ) -> int:
        """Batch update statuses to EXPIRED for provided invitation IDs."""
        if not invitation_ids:
            return 0
        stmt = (
            update(self.model_class)
            .where(
                self.model_class.id.in_(invitation_ids),
                self.model_class.status == InvitationStatus.PENDING.value,
            )
            .values(
                status=InvitationStatus.EXPIRED.value,
                updated_at=updated_at,
            )
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount
