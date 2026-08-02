import logging
from typing import Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.v1.schemas.workspace import (
    ArchiveWorkspaceRequest,
    CreateWorkspaceRequest,
    HardDeleteWorkspaceRequest,
    RestoreDeletedWorkspaceRequest,
    RestoreWorkspaceRequest,
    SoftDeleteWorkspaceRequest,
    SuspendWorkspaceRequest,
    UnsuspendWorkspaceRequest,
    UpdateWorkspaceRequest,
    WorkspaceDataResponse,
    WorkspaceResponse,
)
from backend.api.v1.schemas.workspace_settings import (
    WorkspaceBrandingDataResponse,
    WorkspaceBrandingDiffResponse,
    WorkspaceBrandingPreviewRequest,
    WorkspaceBrandingPublishRequest,
    WorkspaceBrandingResponse,
    WorkspaceBrandingRollbackRequest,
    WorkspaceSettingsDataResponse,
    WorkspaceSettingsHistoryData,
    WorkspaceSettingsHistoryResponse,
    WorkspaceSettingsImportRequest,
    WorkspaceSettingsPatchRequest,
    WorkspaceSettingsResetRequest,
    WorkspaceSettingsResponse,
)
from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user, require_role
from backend.core.dependencies.database import (
    get_db,
    get_workspace_management_service,
    get_workspace_provisioning_service,
    get_workspace_settings_service,
)
from backend.core.permissions.rbac import Role
from backend.services.workspace.management_service import (
    WorkspaceConflictError,
    WorkspaceInvalidStateError,
    WorkspaceManagementService,
    WorkspaceNotFoundError,
    WorkspaceUnauthorizedError,
)
from backend.services.workspace.provisioning_service import WorkspaceProvisioningService
from backend.services.workspace.settings_service import WorkspaceSettingsService

router = APIRouter(prefix="/workspaces", tags=["Workspaces"])
logger = logging.getLogger(__name__)


@router.post(
    "",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new workspace",
)
async def create_workspace(
    request: CreateWorkspaceRequest,
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    provisioning_service: WorkspaceProvisioningService = Depends(get_workspace_provisioning_service),
) -> WorkspaceResponse:
    """Create a new workspace and provision its required resources."""

    # We require the user to be verified
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required to create a workspace.",
        )

    try:
        workspace = await provisioning_service.create_workspace(
            session=session,
            name=request.name,
            user_id=current_user.id,
            description=request.description,
        )

        return WorkspaceResponse(
            success=True,
            data=WorkspaceDataResponse(
                id=workspace.id,
                name=workspace.name,
                slug=workspace.slug,
                description=workspace.description,
                status=workspace.status,
                provisioning_status=workspace.provisioning_status,
                updated_at=workspace.updated_at,
            ),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Failed to create workspace")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating the workspace.",
        ) from e


@router.get(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_200_OK,
    summary="Get workspace details",
)
async def get_workspace(
    workspace_id: uuid.UUID,
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    management_service: WorkspaceManagementService = Depends(get_workspace_management_service),
) -> WorkspaceResponse:
    """Retrieve workspace details by ID."""
    try:
        member = await management_service.workspace_member_repo.get_membership(workspace_id, current_user.id)
        if not member and current_user.role != Role.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found or access denied.",
            )

        workspace = await management_service.workspace_repo.get_by_id(workspace_id)
        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found.",
            )

        return WorkspaceResponse(
            success=True,
            data=WorkspaceDataResponse(
                id=workspace.id,
                name=workspace.name,
                slug=workspace.slug,
                description=workspace.description,
                status=workspace.status,
                provisioning_status=workspace.provisioning_status,
                updated_at=workspace.updated_at,
                suspended_at=workspace.suspended_at,
                deleted_at=workspace.deleted_at,
                purge_at=workspace.purge_at,
                deleted_by_user_id=workspace.deleted_by_user_id,
                deletion_reason_code=workspace.deletion_reason_code,
                deletion_reason_text=workspace.deletion_reason_text,
            ),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get workspace")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching the workspace.",
        ) from e


@router.patch(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_200_OK,
    summary="Update workspace details",
)
async def update_workspace(
    workspace_id: uuid.UUID,
    request: UpdateWorkspaceRequest,
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    management_service: WorkspaceManagementService = Depends(get_workspace_management_service),
) -> WorkspaceResponse:
    """Update workspace name or description with optimistic locking."""
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required to update a workspace.",
        )

    if request.name is None and request.description is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty PATCH request. Must provide name or description to update.",
        )

    try:
        workspace = await management_service.update_workspace(
            session=session,
            workspace_id=workspace_id,
            user_id=current_user.id,
            expected_updated_at=request.expected_updated_at,
            name=request.name,
            description=request.description
        )

        return WorkspaceResponse(
            success=True,
            data=WorkspaceDataResponse(
                id=workspace.id,
                name=workspace.name,
                slug=workspace.slug,
                description=workspace.description,
                status=workspace.status,
                provisioning_status=workspace.provisioning_status,
                updated_at=workspace.updated_at,
                suspended_at=workspace.suspended_at,
                deleted_at=workspace.deleted_at,
                purge_at=workspace.purge_at,
                deleted_by_user_id=workspace.deleted_by_user_id,
                deletion_reason_code=workspace.deletion_reason_code,
                deletion_reason_text=workspace.deletion_reason_text,
            )
        )
    except WorkspaceNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except WorkspaceUnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except WorkspaceInvalidStateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except WorkspaceConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        logger.exception("Failed to update workspace")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating the workspace."
        ) from e


@router.post(
    "/{workspace_id}/archive",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_200_OK,
    summary="Archive workspace",
)
async def archive_workspace(
    workspace_id: uuid.UUID,
    request: ArchiveWorkspaceRequest,
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    management_service: WorkspaceManagementService = Depends(get_workspace_management_service),
) -> WorkspaceResponse:
    """Archive a workspace."""
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required to archive a workspace.",
        )

    try:
        workspace = await management_service.archive_workspace(
            session=session,
            workspace_id=workspace_id,
            user_id=current_user.id,
            expected_updated_at=request.expected_updated_at,
            confirmation_name=request.confirmation_name,
            reason=request.reason
        )

        return WorkspaceResponse(
            success=True,
            data=WorkspaceDataResponse(
                id=workspace.id,
                name=workspace.name,
                slug=workspace.slug,
                description=workspace.description,
                status=workspace.status,
                provisioning_status=workspace.provisioning_status,
                updated_at=workspace.updated_at,
                suspended_at=workspace.suspended_at,
            )
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except WorkspaceNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except WorkspaceUnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except WorkspaceInvalidStateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except WorkspaceConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        logger.exception("Failed to archive workspace")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while archiving the workspace."
        ) from e


@router.post(
    "/{workspace_id}/restore",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_200_OK,
    summary="Restore workspace",
)
async def restore_workspace(
    workspace_id: uuid.UUID,
    request: RestoreWorkspaceRequest,
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    management_service: WorkspaceManagementService = Depends(get_workspace_management_service),
) -> WorkspaceResponse:
    """Restore an archived workspace."""
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required to restore a workspace.",
        )

    try:
        workspace = await management_service.restore_workspace(
            session=session,
            workspace_id=workspace_id,
            user_id=current_user.id,
            expected_updated_at=request.expected_updated_at
        )

        return WorkspaceResponse(
            success=True,
            data=WorkspaceDataResponse(
                id=workspace.id,
                name=workspace.name,
                slug=workspace.slug,
                description=workspace.description,
                status=workspace.status,
                provisioning_status=workspace.provisioning_status,
                updated_at=workspace.updated_at,
                suspended_at=workspace.suspended_at,
            )
        )
    except WorkspaceNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except WorkspaceUnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except WorkspaceInvalidStateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except WorkspaceConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        logger.exception("Failed to restore workspace")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while restoring the workspace."
        ) from e


@router.post(
    "/{workspace_id}/suspend",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_200_OK,
    summary="Suspend workspace (Platform Admin only)",
)
async def suspend_workspace(
    workspace_id: uuid.UUID,
    request: SuspendWorkspaceRequest,
    current_user: UserContext = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_db),
    management_service: WorkspaceManagementService = Depends(get_workspace_management_service),
) -> WorkspaceResponse:
    """Suspend a workspace by Platform Admin."""
    try:
        workspace = await management_service.suspend_workspace(
            session=session,
            workspace_id=workspace_id,
            admin_id=current_user.id,
            admin_email=current_user.email,
            expected_updated_at=request.expected_updated_at,
            confirmation_name=request.confirmation_name,
            reason_code=request.reason_code.value,
            reason_text=request.reason_text,
        )

        return WorkspaceResponse(
            success=True,
            data=WorkspaceDataResponse(
                id=workspace.id,
                name=workspace.name,
                slug=workspace.slug,
                description=workspace.description,
                status=workspace.status,
                provisioning_status=workspace.provisioning_status,
                updated_at=workspace.updated_at,
                suspended_at=workspace.suspended_at,
            )
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except WorkspaceNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except WorkspaceUnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except WorkspaceInvalidStateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except WorkspaceConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        logger.exception("Failed to suspend workspace")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while suspending the workspace."
        ) from e


@router.post(
    "/{workspace_id}/unsuspend",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_200_OK,
    summary="Unsuspend workspace (Platform Admin only)",
)
async def unsuspend_workspace(
    workspace_id: uuid.UUID,
    request: UnsuspendWorkspaceRequest,
    current_user: UserContext = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_db),
    management_service: WorkspaceManagementService = Depends(get_workspace_management_service),
) -> WorkspaceResponse:
    """Unsuspend a workspace by Platform Admin."""
    try:
        workspace = await management_service.unsuspend_workspace(
            session=session,
            workspace_id=workspace_id,
            admin_id=current_user.id,
            admin_email=current_user.email,
            expected_updated_at=request.expected_updated_at,
            reason_text=request.reason_text,
        )

        return WorkspaceResponse(
            success=True,
            data=WorkspaceDataResponse(
                id=workspace.id,
                name=workspace.name,
                slug=workspace.slug,
                description=workspace.description,
                status=workspace.status,
                provisioning_status=workspace.provisioning_status,
                updated_at=workspace.updated_at,
                suspended_at=workspace.suspended_at,
            )
        )
    except WorkspaceNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except WorkspaceUnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except WorkspaceInvalidStateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except WorkspaceConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        logger.exception("Failed to unsuspend workspace")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while unsuspending the workspace."
        ) from e


# ── F3.5 Workspace Soft / Restore / Hard Delete ───────────────────────────────

@router.post(
    "/{workspace_id}/soft-delete",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_200_OK,
    summary="Soft delete workspace (Owner or Platform Admin)",
)
async def soft_delete_workspace(
    workspace_id: uuid.UUID,
    request: SoftDeleteWorkspaceRequest,
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    management_service: WorkspaceManagementService = Depends(get_workspace_management_service),
) -> WorkspaceResponse:
    """Soft delete workspace with 30-day retention grace period."""
    try:
        is_platform_admin = current_user.role == Role.ADMIN
        workspace = await management_service.soft_delete_workspace(
            session=session,
            workspace_id=workspace_id,
            user_id=current_user.id,
            expected_updated_at=request.expected_updated_at,
            confirmation_name=request.confirmation_name,
            reason_code=request.reason_code.value,
            reason_text=request.reason_text,
            is_platform_admin=is_platform_admin,
        )

        return WorkspaceResponse(
            success=True,
            data=WorkspaceDataResponse(
                id=workspace.id,
                name=workspace.name,
                slug=workspace.slug,
                description=workspace.description,
                status=workspace.status,
                provisioning_status=workspace.provisioning_status,
                updated_at=workspace.updated_at,
                suspended_at=workspace.suspended_at,
                deleted_at=workspace.deleted_at,
                purge_at=workspace.purge_at,
                deleted_by_user_id=workspace.deleted_by_user_id,
                deletion_reason_code=workspace.deletion_reason_code,
                deletion_reason_text=workspace.deletion_reason_text,
            ),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except WorkspaceNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except WorkspaceUnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except WorkspaceInvalidStateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except WorkspaceConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        logger.exception("Failed to soft delete workspace")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while soft deleting the workspace.",
        ) from e


@router.post(
    "/{workspace_id}/restore-deleted",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_200_OK,
    summary="Restore soft-deleted workspace (Owner or Platform Admin)",
)
async def restore_deleted_workspace(
    workspace_id: uuid.UUID,
    request: RestoreDeletedWorkspaceRequest,
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    management_service: WorkspaceManagementService = Depends(get_workspace_management_service),
) -> WorkspaceResponse:
    """Restore a soft-deleted workspace to ACTIVE state within the 30-day grace window."""
    try:
        is_platform_admin = current_user.role == Role.ADMIN
        workspace = await management_service.restore_deleted_workspace(
            session=session,
            workspace_id=workspace_id,
            user_id=current_user.id,
            expected_updated_at=request.expected_updated_at,
            is_platform_admin=is_platform_admin,
        )

        return WorkspaceResponse(
            success=True,
            data=WorkspaceDataResponse(
                id=workspace.id,
                name=workspace.name,
                slug=workspace.slug,
                description=workspace.description,
                status=workspace.status,
                provisioning_status=workspace.provisioning_status,
                updated_at=workspace.updated_at,
                suspended_at=workspace.suspended_at,
                deleted_at=workspace.deleted_at,
                purge_at=workspace.purge_at,
                deleted_by_user_id=workspace.deleted_by_user_id,
                deletion_reason_code=workspace.deletion_reason_code,
                deletion_reason_text=workspace.deletion_reason_text,
            ),
        )
    except WorkspaceNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except WorkspaceUnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except WorkspaceInvalidStateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except WorkspaceConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        logger.exception("Failed to restore deleted workspace")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while restoring the deleted workspace.",
        ) from e


@router.post(
    "/{workspace_id}/hard-delete",
    status_code=status.HTTP_200_OK,
    summary="Hard delete workspace immediately (Platform Admin only)",
)
async def hard_delete_workspace(
    workspace_id: uuid.UUID,
    request: HardDeleteWorkspaceRequest,
    current_user: UserContext = Depends(require_role(Role.ADMIN)),
    session: AsyncSession = Depends(get_db),
    management_service: WorkspaceManagementService = Depends(get_workspace_management_service),
) -> dict[str, Any]:
    """Permanently purge a workspace and all its vector/storage resources."""
    try:
        cleanup_metrics = await management_service.hard_delete_workspace(
            session=session,
            workspace_id=workspace_id,
            admin_id=current_user.id,
            confirmation_slug=request.confirmation_slug,
            reason=request.reason,
            force_immediate=request.force_immediate,
        )
        return {"success": True, "data": cleanup_metrics}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except WorkspaceNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except WorkspaceUnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except WorkspaceInvalidStateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Failed to hard delete workspace")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while hard deleting the workspace.",
        ) from e


# ── F3.6 Workspace Settings ───────────────────────────────────────────────────

@router.get(
    "/{workspace_id}/settings",
    response_model=WorkspaceSettingsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get workspace settings",
)
async def get_workspace_settings(
    workspace_id: uuid.UUID,
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings_service: WorkspaceSettingsService = Depends(get_workspace_settings_service),
) -> WorkspaceSettingsResponse:
    """Retrieve full validated workspace settings document."""
    try:
        is_platform_admin = current_user.role == Role.ADMIN
        settings = await settings_service.get_settings(
            session=session,
            workspace_id=workspace_id,
            user_id=current_user.id,
            is_platform_admin=is_platform_admin,
        )
        return WorkspaceSettingsResponse(
            success=True,
            data=WorkspaceSettingsDataResponse(
                workspace_id=settings.workspace_id,
                settings=settings.settings_json,
                schema_version=settings.schema_version,
                version=settings.version,
                settings_hash=settings.settings_hash,
                updated_at=settings.updated_at,
            ),
        )
    except WorkspaceNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.exception("Failed to get workspace settings")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching workspace settings.",
        ) from e


@router.patch(
    "/{workspace_id}/settings",
    response_model=WorkspaceSettingsResponse,
    status_code=status.HTTP_200_OK,
    summary="Patch workspace settings (Owner/Admin)",
)
async def patch_workspace_settings(
    workspace_id: uuid.UUID,
    request: WorkspaceSettingsPatchRequest,
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings_service: WorkspaceSettingsService = Depends(get_workspace_settings_service),
) -> WorkspaceSettingsResponse:
    """Deep merge patch into workspace settings, validate schema, and bump version."""
    try:
        is_platform_admin = current_user.role == Role.ADMIN
        settings = await settings_service.patch_settings(
            session=session,
            workspace_id=workspace_id,
            user_id=current_user.id,
            expected_updated_at=request.expected_updated_at,
            patch_data=request.settings,
            is_platform_admin=is_platform_admin,
        )
        return WorkspaceSettingsResponse(
            success=True,
            data=WorkspaceSettingsDataResponse(
                workspace_id=settings.workspace_id,
                settings=settings.settings_json,
                schema_version=settings.schema_version,
                version=settings.version,
                settings_hash=settings.settings_hash,
                updated_at=settings.updated_at,
            ),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except WorkspaceNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except WorkspaceUnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except WorkspaceConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        logger.exception("Failed to patch workspace settings")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating workspace settings.",
        ) from e


@router.post(
    "/{workspace_id}/settings/reset",
    response_model=WorkspaceSettingsResponse,
    status_code=status.HTTP_200_OK,
    summary="Reset workspace settings to defaults (Owner/Admin)",
)
async def reset_workspace_settings(
    workspace_id: uuid.UUID,
    request: WorkspaceSettingsResetRequest,
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings_service: WorkspaceSettingsService = Depends(get_workspace_settings_service),
) -> WorkspaceSettingsResponse:
    """Reset entire settings document or a specific category to defaults."""
    try:
        is_platform_admin = current_user.role == Role.ADMIN
        settings = await settings_service.reset_settings(
            session=session,
            workspace_id=workspace_id,
            user_id=current_user.id,
            expected_updated_at=request.expected_updated_at,
            category=request.category,
            is_platform_admin=is_platform_admin,
        )
        return WorkspaceSettingsResponse(
            success=True,
            data=WorkspaceSettingsDataResponse(
                workspace_id=settings.workspace_id,
                settings=settings.settings_json,
                schema_version=settings.schema_version,
                version=settings.version,
                settings_hash=settings.settings_hash,
                updated_at=settings.updated_at,
            ),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except WorkspaceNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except WorkspaceUnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except WorkspaceConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        logger.exception("Failed to reset workspace settings")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while resetting workspace settings.",
        ) from e


@router.get(
    "/{workspace_id}/settings/export",
    response_model=WorkspaceSettingsResponse,
    status_code=status.HTTP_200_OK,
    summary="Export workspace settings (Owner/Admin)",
)
async def export_workspace_settings(
    workspace_id: uuid.UUID,
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings_service: WorkspaceSettingsService = Depends(get_workspace_settings_service),
) -> WorkspaceSettingsResponse:
    """Export complete workspace configuration with metadata."""
    try:
        is_platform_admin = current_user.role == Role.ADMIN
        settings = await settings_service.get_settings(
            session=session,
            workspace_id=workspace_id,
            user_id=current_user.id,
            is_platform_admin=is_platform_admin,
        )
        return WorkspaceSettingsResponse(
            success=True,
            data=WorkspaceSettingsDataResponse(
                workspace_id=settings.workspace_id,
                settings=settings.settings_json,
                schema_version=settings.schema_version,
                version=settings.version,
                settings_hash=settings.settings_hash,
                updated_at=settings.updated_at,
            ),
        )
    except WorkspaceNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.exception("Failed to export workspace settings")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while exporting workspace settings.",
        ) from e


@router.post(
    "/{workspace_id}/settings/import",
    status_code=status.HTTP_200_OK,
    summary="Import workspace settings with optional dry_run (Owner/Admin)",
)
async def import_workspace_settings(
    workspace_id: uuid.UUID,
    request: WorkspaceSettingsImportRequest,
    dry_run: bool = Query(False, description="If true, validate without persisting changes"),
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings_service: WorkspaceSettingsService = Depends(get_workspace_settings_service),
) -> dict[str, Any]:
    """Import and validate settings configuration."""
    try:
        is_platform_admin = current_user.role == Role.ADMIN
        result = await settings_service.import_settings(
            session=session,
            workspace_id=workspace_id,
            user_id=current_user.id,
            expected_updated_at=request.expected_updated_at,
            import_payload=request.settings,
            dry_run=dry_run,
            is_platform_admin=is_platform_admin,
        )
        return {"success": True, "data": result}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except WorkspaceNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except WorkspaceUnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except WorkspaceConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        logger.exception("Failed to import workspace settings")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while importing workspace settings.",
        ) from e


@router.get(
    "/{workspace_id}/settings/history",
    response_model=WorkspaceSettingsHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get settings change history snapshots",
)
async def get_workspace_settings_history(
    workspace_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=100),
    current_user: UserContext = Depends(get_current_user),
    settings_service: WorkspaceSettingsService = Depends(get_workspace_settings_service),
) -> WorkspaceSettingsHistoryResponse:
    """Retrieve version history snapshots for workspace settings."""
    try:
        is_platform_admin = current_user.role == Role.ADMIN
        history = await settings_service.get_history(
            workspace_id=workspace_id,
            user_id=current_user.id,
            limit=limit,
            is_platform_admin=is_platform_admin,
        )
        return WorkspaceSettingsHistoryResponse(
            success=True,
            data=[
                WorkspaceSettingsHistoryData(
                    id=h.id,
                    workspace_id=h.workspace_id,
                    settings=h.settings_json,
                    schema_version=h.schema_version,
                    version=h.version,
                    settings_hash=h.settings_hash,
                    changed_by_user_id=h.changed_by_user_id,
                    change_reason=h.change_reason,
                    created_at=h.created_at,
                )
                for h in history
            ],
        )
    except WorkspaceNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.exception("Failed to fetch settings history")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching settings history.",
        ) from e


# ── F3.7 Workspace Branding Endpoints ────────────────────────────────────────

@router.get(
    "/{workspace_id}/branding",
    response_model=WorkspaceBrandingResponse,
    status_code=status.HTTP_200_OK,
    summary="Get resolved workspace branding and CSS variables",
)
async def get_workspace_branding(
    workspace_id: uuid.UUID,
    preview: bool = Query(False, description="Whether to include staged draft preview branding"),
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings_service: WorkspaceSettingsService = Depends(get_workspace_settings_service),
) -> WorkspaceBrandingResponse:
    """Fetch resolved branding configuration with compiled CSS variables and Tailwind tokens."""
    try:
        is_platform_admin = current_user.role == Role.ADMIN
        branding_data = await settings_service.get_resolved_branding(
            session=session,
            workspace_id=workspace_id,
            user_id=current_user.id,
            is_preview=preview,
            is_platform_admin=is_platform_admin,
        )
        return WorkspaceBrandingResponse(
            success=True,
            data=WorkspaceBrandingDataResponse(**branding_data),
        )
    except WorkspaceNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.exception("Failed to fetch workspace branding")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching workspace branding.",
        ) from e


@router.post(
    "/{workspace_id}/branding/preview",
    response_model=WorkspaceBrandingResponse,
    status_code=status.HTTP_200_OK,
    summary="Stage draft branding preview in Redis",
)
async def stage_branding_preview(
    workspace_id: uuid.UUID,
    request: WorkspaceBrandingPreviewRequest,
    current_user: UserContext = Depends(get_current_user),
    settings_service: WorkspaceSettingsService = Depends(get_workspace_settings_service),
) -> WorkspaceBrandingResponse:
    """Stage draft branding configuration in Redis without affecting production."""
    try:
        is_platform_admin = current_user.role == Role.ADMIN
        preview_data = await settings_service.stage_branding_preview(
            workspace_id=workspace_id,
            user_id=current_user.id,
            branding_dict=request.branding.model_dump(mode="json"),
            is_platform_admin=is_platform_admin,
        )
        return WorkspaceBrandingResponse(
            success=True,
            data=WorkspaceBrandingDataResponse(**preview_data),
        )
    except WorkspaceUnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        logger.exception("Failed to stage branding preview")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while staging branding preview.",
        ) from e


@router.post(
    "/{workspace_id}/branding/publish",
    response_model=WorkspaceBrandingResponse,
    status_code=status.HTTP_200_OK,
    summary="Publish branding configuration to production",
)
async def publish_branding(
    workspace_id: uuid.UUID,
    request: WorkspaceBrandingPublishRequest,
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings_service: WorkspaceSettingsService = Depends(get_workspace_settings_service),
) -> WorkspaceBrandingResponse:
    """Publish and commit branding configuration, invalidating CDN/browser cache."""
    try:
        is_platform_admin = current_user.role == Role.ADMIN
        await settings_service.publish_branding(
            session=session,
            workspace_id=workspace_id,
            user_id=current_user.id,
            expected_updated_at=request.expected_updated_at,
            branding_dict=request.branding.model_dump(mode="json"),
            change_reason=request.change_reason,
            is_platform_admin=is_platform_admin,
        )
        resolved = await settings_service.get_resolved_branding(
            session=session,
            workspace_id=workspace_id,
            user_id=current_user.id,
            is_preview=False,
            is_platform_admin=is_platform_admin,
        )
        return WorkspaceBrandingResponse(
            success=True,
            data=WorkspaceBrandingDataResponse(**resolved),
        )
    except WorkspaceUnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except WorkspaceConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        logger.exception("Failed to publish branding")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while publishing branding.",
        ) from e


@router.post(
    "/{workspace_id}/branding/rollback",
    response_model=WorkspaceBrandingResponse,
    status_code=status.HTTP_200_OK,
    summary="Rollback branding to a historical version",
)
async def rollback_branding(
    workspace_id: uuid.UUID,
    request: WorkspaceBrandingRollbackRequest,
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    settings_service: WorkspaceSettingsService = Depends(get_workspace_settings_service),
) -> WorkspaceBrandingResponse:
    """Rollback workspace branding to a specific historical snapshot."""
    try:
        is_platform_admin = current_user.role == Role.ADMIN
        await settings_service.rollback_branding(
            session=session,
            workspace_id=workspace_id,
            user_id=current_user.id,
            expected_updated_at=request.expected_updated_at,
            target_version=request.target_version,
            change_reason=request.change_reason,
            is_platform_admin=is_platform_admin,
        )
        resolved = await settings_service.get_resolved_branding(
            session=session,
            workspace_id=workspace_id,
            user_id=current_user.id,
            is_preview=False,
            is_platform_admin=is_platform_admin,
        )
        return WorkspaceBrandingResponse(
            success=True,
            data=WorkspaceBrandingDataResponse(**resolved),
        )
    except WorkspaceUnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except WorkspaceConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Failed to rollback branding")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while rolling back branding.",
        ) from e


@router.get(
    "/{workspace_id}/branding/diff",
    response_model=WorkspaceBrandingDiffResponse,
    status_code=status.HTTP_200_OK,
    summary="View diff between two historical branding versions",
)
async def diff_workspace_branding(
    workspace_id: uuid.UUID,
    from_version: int = Query(..., ge=1, description="Source historical version"),
    to_version: int = Query(..., ge=1, description="Target historical version"),
    current_user: UserContext = Depends(get_current_user),
    settings_service: WorkspaceSettingsService = Depends(get_workspace_settings_service),
) -> WorkspaceBrandingDiffResponse:
    """Compare branding properties across two historical snapshots."""
    try:
        is_platform_admin = current_user.role == Role.ADMIN
        diff_data = await settings_service.diff_branding(
            workspace_id=workspace_id,
            user_id=current_user.id,
            from_version=from_version,
            to_version=to_version,
            is_platform_admin=is_platform_admin,
        )
        return WorkspaceBrandingDiffResponse(
            success=True,
            **diff_data,
        )
    except WorkspaceNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Failed to diff branding versions")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while computing branding diff.",
        ) from e

