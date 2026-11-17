"""Workspace Ownership Transfer Repository.

Handles persistence, lookup, row locking (L5 in canonical lock hierarchy),
and querying for WorkspaceOwnershipTransfer entities.
Governed by Section 7 Batch 1, 2, and 3.
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models.entities.workspace_ownership_transfer import (
    TransferStatus,
    WorkspaceOwnershipTransfer,
)
from backend.repositories.base import BaseRepository


class WorkspaceOwnershipTransferRepository(BaseRepository[WorkspaceOwnershipTransfer]):
    """Repository managing WorkspaceOwnershipTransfer entities with canonical locking."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, WorkspaceOwnershipTransfer)

    async def get_by_id(
        self,
        transfer_id: uuid.UUID,
        for_update: bool = False,
    ) -> Optional[WorkspaceOwnershipTransfer]:
        """Fetch transfer by ID, optionally acquiring an L5 row lock."""
        stmt = (
            select(self.model_class)
            .where(self.model_class.id == transfer_id)
            .options(
                selectinload(self.model_class.nominated_by),
                selectinload(self.model_class.nominee),
                selectinload(self.model_class.workspace),
                selectinload(self.model_class.former_owner_departure),
            )
        )
        if for_update:
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_pending_transfer(
        self,
        workspace_id: uuid.UUID,
        for_update: bool = False,
    ) -> Optional[WorkspaceOwnershipTransfer]:
        """Fetch the active PENDING ownership nomination for a workspace, if any."""
        stmt = (
            select(self.model_class)
            .where(
                self.model_class.workspace_id == workspace_id,
                self.model_class.status == TransferStatus.PENDING.value,
            )
            .options(
                selectinload(self.model_class.nominated_by),
                selectinload(self.model_class.nominee),
            )
        )
        if for_update:
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_workspace(
        self,
        workspace_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[WorkspaceOwnershipTransfer]:
        """Fetch transfer history for a workspace ordered by creation date."""
        stmt = (
            select(self.model_class)
            .where(self.model_class.workspace_id == workspace_id)
            .options(
                selectinload(self.model_class.nominated_by),
                selectinload(self.model_class.nominee),
                selectinload(self.model_class.former_owner_departure),
            )
            .order_by(desc(self.model_class.created_at))
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_pending_by_user(
        self,
        user_id: uuid.UUID,
    ) -> Sequence[WorkspaceOwnershipTransfer]:
        """Fetch all pending incoming nominations for a user."""
        stmt = (
            select(self.model_class)
            .where(
                self.model_class.nominee_user_id == user_id,
                self.model_class.status == TransferStatus.PENDING.value,
            )
            .options(selectinload(self.model_class.workspace))
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
