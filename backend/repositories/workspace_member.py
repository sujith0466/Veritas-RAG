import uuid
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from backend.models.entities.workspace_member import WorkspaceMember
from backend.models.entities.workspace import Workspace
from backend.repositories.base import BaseRepository


class WorkspaceMemberRepository(BaseRepository[WorkspaceMember]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, WorkspaceMember)

    async def get_user_workspaces(self, user_id: uuid.UUID) -> List[Workspace]:
        stmt = (
            select(Workspace)
            .join(WorkspaceMember, Workspace.id == WorkspaceMember.workspace_id)
            .where(
                WorkspaceMember.user_id == user_id,
                WorkspaceMember.is_deleted == False,
                Workspace.is_deleted == False
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_membership(
        self, workspace_id: uuid.UUID, user_id: uuid.UUID
    ) -> Optional[WorkspaceMember]:
        stmt = select(self.model_class).where(
            self.model_class.workspace_id == workspace_id,
            self.model_class.user_id == user_id,
            self.model_class.is_deleted == False
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()
