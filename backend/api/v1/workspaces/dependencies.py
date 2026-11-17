"""FastAPI dependencies for workspace ownership transfer endpoints.
Governed by Section 7 Batch 1 (REV5).
"""

import uuid

from fastapi import Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import get_db
from backend.core.dependencies.workspace import get_workspace_member_or_raise
from backend.models.entities.workspace_member import WorkspaceMember, WorkspaceRole


async def require_active_workspace_owner(
    workspace_id: uuid.UUID = Path(..., description="The workspace ID"),
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> WorkspaceMember:
    """Pre-lock route guard: Verify authenticated caller is an ACTIVE workspace OWNER.

    Provides Layer 1 fast-path rejection before entering the transactional service layer.
    """
    member = await get_workspace_member_or_raise(workspace_id, current_user, session)
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You are not an active member of this workspace.",
        )
    role_str = (member.role or "").strip().upper()
    if role_str != WorkspaceRole.OWNER.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Operation restricted to active workspace OWNER.",
        )
    return member


async def require_active_workspace_member(
    workspace_id: uuid.UUID = Path(..., description="The workspace ID"),
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> WorkspaceMember:
    """Pre-lock route guard: Verify authenticated caller is an ACTIVE workspace member."""
    member = await get_workspace_member_or_raise(workspace_id, current_user, session)
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You are not an active member of this workspace.",
        )
    return member
