from collections.abc import Callable, Coroutine
from typing import Any
import uuid

from fastapi import Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.dependencies.database import get_db
from backend.models.entities.workspace import Workspace, WorkspaceStatus
from backend.repositories.workspace import WorkspaceRepository


async def get_workspace_repository(session: AsyncSession = Depends(get_db)) -> WorkspaceRepository:
    return WorkspaceRepository(session)

def require_active_workspace() -> Callable[..., Coroutine[Any, Any, Workspace]]:
    """Dependency requirement ensuring the specified workspace is ACTIVE."""
    async def _active_workspace_guard(
        workspace_id: uuid.UUID = Path(..., description="The ID of the workspace"),
        repo: WorkspaceRepository = Depends(get_workspace_repository)
    ) -> Workspace:
        workspace = await repo.get_by_id(workspace_id)
        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found."
            )

        if workspace.status != WorkspaceStatus.ACTIVE.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Workspace is {workspace.status}. This operation is not allowed."
            )

        return workspace

    return _active_workspace_guard
