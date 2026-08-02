import uuid
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.entities.workspace_settings import WorkspaceSettings
from backend.repositories.base import BaseRepository


class WorkspaceSettingsRepository(BaseRepository[WorkspaceSettings]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, WorkspaceSettings)

    async def get_by_workspace_id(self, workspace_id: uuid.UUID) -> Optional[WorkspaceSettings]:
        stmt = select(self.model_class).where(
            self.model_class.workspace_id == workspace_id,
            self.model_class.is_deleted == False
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_workspace_id_for_update(self, workspace_id: uuid.UUID) -> Optional[WorkspaceSettings]:
        stmt = select(self.model_class).where(
            self.model_class.workspace_id == workspace_id,
            self.model_class.is_deleted == False
        ).with_for_update()
        result = await self.session.execute(stmt)
        return result.scalars().first()

