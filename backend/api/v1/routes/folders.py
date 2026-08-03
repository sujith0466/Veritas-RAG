"""Folder Management API Routes."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.api.v1.schemas.folder import (
    FolderCreateRequest,
    FolderRenameRequest,
    FolderResponse,
    DeletionQueuedResponse,
    RestoreQueuedResponse,
    FolderStatsResponse,
)
from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user, require_role
from backend.core.dependencies.database import get_folder_service
from backend.core.permissions.rbac import Role
from backend.services.folder_service import (
    FolderService,
    FolderConflictError,
    FolderNotFoundError,
    FolderRateLimitError,
    FolderParentDeletedError,
)

router = APIRouter(prefix="/workspaces/{workspace_id}/folders", tags=["Folders"])


@router.post(
    "",
    response_model=FolderResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(Role.ADMIN, Role.MEMBER))]
)
async def create_folder(
    workspace_id: uuid.UUID,
    request: FolderCreateRequest,
    user: UserContext = Depends(get_current_user),
    service: FolderService = Depends(get_folder_service),
):
    """Create a new folder."""
    try:
        folder = await service.create_folder(
            workspace_id=workspace_id,
            actor_id=user.user_id,
            name=request.name,
            parent_id=request.parent_id,
        )
        return folder
    except FolderConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except FolderNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except FolderRateLimitError as e:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))


@router.patch(
    "/{folder_id}",
    response_model=FolderResponse,
    dependencies=[Depends(require_role(Role.ADMIN, Role.MEMBER))]
)
async def rename_folder(
    workspace_id: uuid.UUID,
    folder_id: uuid.UUID,
    request: FolderRenameRequest,
    user: UserContext = Depends(get_current_user),
    service: FolderService = Depends(get_folder_service),
):
    """Rename a folder."""
    try:
        folder = await service.rename_folder(
            workspace_id=workspace_id,
            actor_id=user.user_id,
            folder_id=folder_id,
            new_name=request.name,
            expected_version=request.version,
        )
        return folder
    except FolderConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except FolderNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete(
    "/{folder_id}",
    response_model=DeletionQueuedResponse,
    dependencies=[Depends(require_role(Role.ADMIN))]
)
async def soft_delete_folder(
    workspace_id: uuid.UUID,
    folder_id: uuid.UUID,
    version: int = Query(..., description="Expected version for optimistic concurrency"),
    user: UserContext = Depends(get_current_user),
    service: FolderService = Depends(get_folder_service),
):
    """Soft delete a folder and all its children."""
    try:
        task_id = await service.soft_delete_folder(
            workspace_id=workspace_id,
            actor_id=user.user_id,
            folder_id=folder_id,
            expected_version=version,
        )
        return DeletionQueuedResponse(folder_id=folder_id, worker_task_id=task_id if task_id != "duplicate" else None)
    except FolderConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except FolderNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/{folder_id}/restore",
    response_model=RestoreQueuedResponse,
    dependencies=[Depends(require_role(Role.ADMIN))]
)
async def restore_folder(
    workspace_id: uuid.UUID,
    folder_id: uuid.UUID,
    user: UserContext = Depends(get_current_user),
    service: FolderService = Depends(get_folder_service),
):
    """Restore a soft-deleted folder and all its previously deleted children."""
    try:
        task_id = await service.restore_folder(
            workspace_id=workspace_id,
            actor_id=user.user_id,
            folder_id=folder_id,
        )
        return RestoreQueuedResponse(folder_id=folder_id, worker_task_id=task_id if task_id != "duplicate" else None)
    except FolderConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except FolderParentDeletedError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except FolderNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/{folder_id}/stats",
    response_model=FolderStatsResponse,
    dependencies=[Depends(require_role(Role.ADMIN, Role.MEMBER))]
)
async def get_folder_stats(
    workspace_id: uuid.UUID,
    folder_id: uuid.UUID,
    service: FolderService = Depends(get_folder_service),
):
    """Get folder statistics like descendant count and document count."""
    try:
        stats = await service.get_folder_stats(
            workspace_id=workspace_id,
            folder_id=folder_id,
        )
        return stats
    except FolderNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


from backend.api.v1.schemas.folder import FolderMoveRequest, FolderMoveResponse, FolderHardDeleteRequest, FolderPurgeStatusResponse

@router.post(
    "/{folder_id}/move",
    response_model=FolderMoveResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_role(Role.ADMIN, Role.MEMBER))]
)
async def move_folder(
    workspace_id: uuid.UUID,
    folder_id: uuid.UUID,
    request: FolderMoveRequest,
    user: UserContext = Depends(get_current_user),
    service: FolderService = Depends(get_folder_service),
):
    """Move a folder to a new parent."""
    try:
        result = await service.move_folder(
            workspace_id=workspace_id,
            actor_id=user.user_id,
            folder_id=folder_id,
            new_parent_id=request.target_parent_id,
            expected_version=request.version,
        )
        return FolderMoveResponse(
            status=result["status"],
            worker_task_id=result.get("worker_task_id"),
            cascade_pending=result.get("cascade_pending", False)
        )
    except FolderConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except FolderNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete(
    "/{folder_id}/hard-delete",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_role(Role.ADMIN))]
)
async def early_hard_delete_folder(
    workspace_id: uuid.UUID,
    folder_id: uuid.UUID,
    request: FolderHardDeleteRequest,
    user: UserContext = Depends(get_current_user),
    service: FolderService = Depends(get_folder_service),
):
    """Force an early hard delete of a soft-deleted folder."""
    try:
        result = await service.early_hard_delete_folder(
            workspace_id=workspace_id,
            actor_id=user.user_id,
            folder_id=folder_id,
            confirmation_name=request.confirmation_name
        )
        return result
    except FolderConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except FolderNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/{folder_id}/purge-status",
    response_model=FolderPurgeStatusResponse,
    dependencies=[Depends(require_role(Role.ADMIN, Role.MEMBER))]
)
async def get_purge_status(
    workspace_id: uuid.UUID,
    folder_id: uuid.UUID,
    user: UserContext = Depends(get_current_user),
    service: FolderService = Depends(get_folder_service),
):
    """Get retention status of a folder."""
    folder = await service.repo.get_by_id_in_workspace(folder_id, workspace_id)
    if folder:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Folder is active.")
        
    from sqlalchemy import select
    from backend.models.entities.folder import Folder
    stmt = select(Folder).where(
        Folder.id == folder_id,
        Folder.workspace_id == workspace_id,
        Folder.is_deleted.is_(True)
    )
    result = await service.session.execute(stmt)
    deleted_folder = result.scalar_one_or_none()
    
    if not deleted_folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found.")
        
    days_until_purge = None
    if deleted_folder.purge_at:
        from datetime import datetime, UTC
        delta = deleted_folder.purge_at - datetime.now(UTC)
        days_until_purge = max(0, delta.days)
        
    return FolderPurgeStatusResponse(
        folder_id=deleted_folder.id,
        is_deleted=deleted_folder.is_deleted,
        deleted_at=deleted_folder.deleted_at,
        purge_at=deleted_folder.purge_at,
        purge_status=deleted_folder.purge_status,
        purge_started_at=deleted_folder.purge_started_at,
        purge_completed_at=deleted_folder.purge_completed_at,
        days_until_purge=days_until_purge
    )
