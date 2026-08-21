import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.entities.workspace import ProvisioningStatus, Workspace
from backend.repositories.base import BaseRepository


class WorkspaceRepository(BaseRepository[Workspace]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Workspace)

    async def exists_by_slug(self, slug: str) -> bool:
        stmt = select(self.model_class.id).where(
            self.model_class.slug == slug,
            self.model_class.is_deleted == False
        )
        result = await self.session.execute(stmt)
        return result.scalars().first() is not None

    async def get_by_slug(self, slug: str) -> Workspace | None:
        stmt = select(self.model_class).where(
            self.model_class.slug == slug,
            self.model_class.is_deleted == False
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def update_provisioning_status(
        self, workspace_id: uuid.UUID, status: ProvisioningStatus
    ) -> Workspace | None:
        workspace = await self.get_by_id(workspace_id)
        if workspace:
            workspace.provisioning_status = status.value
            self.session.add(workspace)
            await self.session.flush()
        return workspace

    async def delete(self, workspace_id: uuid.UUID) -> bool:
        workspace = await self.get_by_id(workspace_id)
        if workspace:
            await self.hard_delete(workspace)
            return True
        return False

