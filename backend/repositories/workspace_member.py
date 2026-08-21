"""Workspace Member Repository.

Handles persistence, lookup, keyset pagination, and row locking for WorkspaceMember entities.
"""

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models.entities.user import User
from backend.models.entities.workspace import Workspace
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember, WorkspaceRole
from backend.repositories.base import BaseRepository


class WorkspaceMemberRepository(BaseRepository[WorkspaceMember]):
    """Repository for managing WorkspaceMember entities."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, WorkspaceMember)

    async def get_user_workspaces(self, user_id: uuid.UUID) -> list[Workspace]:
        """Fetch all active workspaces associated with a user."""
        stmt = (
            select(Workspace)
            .join(WorkspaceMember, Workspace.id == WorkspaceMember.workspace_id)
            .where(
                WorkspaceMember.user_id == user_id,
                WorkspaceMember.status == MemberStatus.ACTIVE.value,
                WorkspaceMember.is_deleted == False,
                Workspace.is_deleted == False,
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_membership(
        self, workspace_id: uuid.UUID, user_id: uuid.UUID, include_suspended: bool = True
    ) -> WorkspaceMember | None:
        """Fetch a user's membership in a specific workspace."""
        conditions = [
            self.model_class.workspace_id == workspace_id,
            self.model_class.user_id == user_id,
            self.model_class.is_deleted == False,
        ]
        if not include_suspended:
            conditions.append(self.model_class.status == MemberStatus.ACTIVE.value)

        stmt = (
            select(self.model_class)
            .options(
                selectinload(self.model_class.user),
                selectinload(self.model_class.invited_by),
            )
            .where(*conditions)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_membership_for_update(
        self, workspace_id: uuid.UUID, user_id: uuid.UUID
    ) -> WorkspaceMember | None:
        """Fetch a membership record with pessimistic row lock (SELECT FOR UPDATE)."""
        stmt = (
            select(self.model_class)
            .options(
                selectinload(self.model_class.user),
                selectinload(self.model_class.invited_by),
            )
            .where(
                self.model_class.workspace_id == workspace_id,
                self.model_class.user_id == user_id,
                self.model_class.is_deleted == False,
            )
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_id(
        self, member_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> WorkspaceMember | None:
        """Fetch a member by primary key with tenant boundary check."""
        stmt = (
            select(self.model_class)
            .options(
                selectinload(self.model_class.user),
                selectinload(self.model_class.invited_by),
            )
            .where(
                self.model_class.id == member_id,
                self.model_class.workspace_id == workspace_id,
                self.model_class.is_deleted == False,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_id_for_update(
        self, member_id: uuid.UUID, workspace_id: uuid.UUID
    ) -> WorkspaceMember | None:
        """Fetch a member by primary key with pessimistic row lock."""
        stmt = (
            select(self.model_class)
            .options(
                selectinload(self.model_class.user),
                selectinload(self.model_class.invited_by),
            )
            .where(
                self.model_class.id == member_id,
                self.model_class.workspace_id == workspace_id,
                self.model_class.is_deleted == False,
            )
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def count_active_owners(self, workspace_id: uuid.UUID) -> int:
        """Count total active owners in a workspace for Last Owner Protection."""
        stmt = select(func.count(self.model_class.id)).where(
            self.model_class.workspace_id == workspace_id,
            self.model_class.role == WorkspaceRole.OWNER.value,
            self.model_class.status == MemberStatus.ACTIVE.value,
            self.model_class.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def list_members(
        self,
        workspace_id: uuid.UUID,
        search: str | None = None,
        role: str | None = None,
        status: str | None = None,
        cursor: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[WorkspaceMember], int, str | None]:
        """
        List members with search, filters, total count, and cursor/offset support.

        Returns:
            Tuple[List[WorkspaceMember], int, Optional[str]]: (items, total_count, next_cursor)
        """
        base_conditions = [
            self.model_class.workspace_id == workspace_id,
            self.model_class.is_deleted == False,
        ]

        if role:
            base_conditions.append(self.model_class.role == role.strip().upper())
        if status:
            base_conditions.append(self.model_class.status == status.strip().upper())

        # Search against User email and username
        search_filter = None
        if search and search.strip():
            s = f"%{search.strip().lower()}%"
            search_filter = or_(
                func.lower(User.email).like(s),
                func.lower(User.username).like(s),
            )

        # Count total
        count_stmt = (
            select(func.count(self.model_class.id))
            .join(User, self.model_class.user_id == User.id)
            .where(*base_conditions)
        )
        if search_filter is not None:
            count_stmt = count_stmt.where(search_filter)

        count_res = await self.session.execute(count_stmt)
        total = count_res.scalar() or 0

        # Query items
        query_stmt = (
            select(self.model_class)
            .join(User, self.model_class.user_id == User.id)
            .options(
                selectinload(self.model_class.user),
                selectinload(self.model_class.invited_by),
            )
            .where(*base_conditions)
        )
        if search_filter is not None:
            query_stmt = query_stmt.where(search_filter)

        query_stmt = query_stmt.order_by(self.model_class.created_at.desc(), self.model_class.id.desc())
        query_stmt = query_stmt.offset(skip).limit(limit)

        result = await self.session.execute(query_stmt)
        items = list(result.scalars().all())

        next_cursor = None
        if len(items) == limit:
            last_item = items[-1]
            next_cursor = f"{last_item.created_at.isoformat()}_{last_item.id!s}"

        return items, total, next_cursor
