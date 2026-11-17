"""Workspace Former Owner Departure Repository.

Handles persistence, lookup, and row locking for WorkspaceFormerOwnerDeparture entities.
Governed by Section 7 Batch 3 (WP 7.10, PO-D32-03).
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models.entities.workspace_former_owner_departure import (
    FormerOwnerDepartureType,
    WorkspaceFormerOwnerDeparture,
)
from backend.repositories.base import BaseRepository


class WorkspaceFormerOwnerDepartureRepository(BaseRepository[WorkspaceFormerOwnerDeparture]):
    """Repository managing immutable WorkspaceFormerOwnerDeparture records."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, WorkspaceFormerOwnerDeparture)

    async def create_departure(
        self,
        workspace_id: uuid.UUID,
        former_owner_id: uuid.UUID,
        transfer_id: uuid.UUID,
        departure_type: FormerOwnerDepartureType | str,
        confirmed_by_user_id: uuid.UUID,
        departure_confirmed_at: datetime,
        former_role: str = "OWNER",
        retained_role: Optional[str] = None,
        departure_notes: Optional[str] = None,
    ) -> WorkspaceFormerOwnerDeparture:
        """Create and persist a new former owner departure record."""
        dep_type_val = (
            departure_type.value
            if isinstance(departure_type, FormerOwnerDepartureType)
            else str(departure_type)
        )
        record = WorkspaceFormerOwnerDeparture(
            workspace_id=workspace_id,
            former_owner_id=former_owner_id,
            transfer_id=transfer_id,
            departure_type=dep_type_val,
            former_role=former_role,
            retained_role=retained_role,
            confirmed_by_user_id=confirmed_by_user_id,
            departure_confirmed_at=departure_confirmed_at,
            departure_notes=departure_notes,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def get_by_id(
        self,
        departure_id: uuid.UUID,
        for_update: bool = False,
    ) -> Optional[WorkspaceFormerOwnerDeparture]:
        """Fetch departure record by primary key, optionally acquiring L6 row lock."""
        stmt = (
            select(self.model_class)
            .where(self.model_class.id == departure_id)
            .options(
                selectinload(self.model_class.former_owner),
                selectinload(self.model_class.confirmed_by),
                selectinload(self.model_class.workspace),
            )
        )
        if for_update:
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_transfer_id(
        self,
        transfer_id: uuid.UUID,
        for_update: bool = False,
    ) -> Optional[WorkspaceFormerOwnerDeparture]:
        """Fetch departure record by unique transfer ID."""
        stmt = (
            select(self.model_class)
            .where(self.model_class.transfer_id == transfer_id)
            .options(
                selectinload(self.model_class.former_owner),
                selectinload(self.model_class.confirmed_by),
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
    ) -> Sequence[WorkspaceFormerOwnerDeparture]:
        """Fetch historical departure records for a workspace ordered by departure timestamp."""
        stmt = (
            select(self.model_class)
            .where(self.model_class.workspace_id == workspace_id)
            .options(
                selectinload(self.model_class.former_owner),
                selectinload(self.model_class.confirmed_by),
            )
            .order_by(desc(self.model_class.departure_confirmed_at))
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_by_former_owner(
        self,
        former_owner_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[WorkspaceFormerOwnerDeparture]:
        """Fetch historical departure records for a specific former owner."""
        stmt = (
            select(self.model_class)
            .where(self.model_class.former_owner_id == former_owner_id)
            .options(selectinload(self.model_class.workspace))
            .order_by(desc(self.model_class.departure_confirmed_at))
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
