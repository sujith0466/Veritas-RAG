from collections.abc import Callable, Coroutine
from typing import Any
import uuid

from fastapi import Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import get_db
from backend.core.permissions.rbac import Role
from backend.models.entities.workspace import Workspace, WorkspaceStatus
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember
from backend.repositories.workspace import WorkspaceRepository
from backend.repositories.workspace_member import WorkspaceMemberRepository


async def get_workspace_repository(session: AsyncSession = Depends(get_db)) -> WorkspaceRepository:
    return WorkspaceRepository(session)


async def get_workspace_member_repository(session: AsyncSession = Depends(get_db)) -> WorkspaceMemberRepository:
    return WorkspaceMemberRepository(session)


async def get_workspace_member_or_raise(
    workspace_id: uuid.UUID,
    current_user: UserContext,
    session: AsyncSession,
) -> WorkspaceMember | None:
    """Verify authenticated user is an ACTIVE member of the target workspace.

    Canonical workspace authorization model:
        authenticated user -> WorkspaceMember -> target workspace_id.
    Platform Admins possess global system privileges.
    """
    user_role = Role.from_str(current_user.role) if isinstance(current_user.role, str) else current_user.role
    if user_role == Role.PLATFORM_ADMIN:
        return None

    repo = WorkspaceMemberRepository(session)
    member = await repo.get_membership(workspace_id=workspace_id, user_id=current_user.id, include_suspended=False)
    if not member or member.status != MemberStatus.ACTIVE.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You are not an active member of this workspace.",
        )
    return member


def require_workspace_membership() -> Callable[..., Coroutine[Any, Any, WorkspaceMember | None]]:
    """FastAPI dependency to authorize access to a workspace via canonical membership lookup."""
    async def _membership_guard(
        workspace_id: uuid.UUID = Path(..., description="The ID of the workspace"),
        current_user: UserContext = Depends(get_current_user),
        session: AsyncSession = Depends(get_db),
    ) -> WorkspaceMember | None:
        return await get_workspace_member_or_raise(workspace_id, current_user, session)

    return _membership_guard


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
