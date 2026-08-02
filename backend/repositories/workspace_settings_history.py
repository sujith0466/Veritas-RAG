from collections.abc import Sequence
import uuid

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.entities.workspace_settings_history import WorkspaceSettingsHistory
from backend.repositories.base import BaseRepository


class WorkspaceSettingsHistoryRepository(BaseRepository[WorkspaceSettingsHistory]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, WorkspaceSettingsHistory)

    async def list_by_workspace_id(
        self, workspace_id: uuid.UUID, limit: int = 50
    ) -> Sequence[WorkspaceSettingsHistory]:
        stmt = (
            select(self.model_class)
            .where(
                self.model_class.workspace_id == workspace_id,
                self.model_class.is_deleted == False,
            )
            .order_by(desc(self.model_class.created_at))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
