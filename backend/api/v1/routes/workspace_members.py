"""Workspace Members API Endpoints.

Provides endpoints for listing, updating role, suspending, restoring, removing,
and bulk managing members within a workspace.
"""

import uuid

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.api.v1.schemas.workspace_member import (
    BulkMemberActionRequest,
    BulkMemberActionResponse,
    BulkMemberActionResult,
    UpdateMemberRoleRequest,
    WorkspaceMemberData,
    WorkspaceMemberListResponse,
    WorkspaceMemberResponse,
)
from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import (
    get_db,
    get_workspace_membership_service,
)
from backend.core.permissions.guards import record_diagnostic_access, validate_diagnostic_ticket
from backend.core.permissions.rbac import Role
from backend.services.workspace.membership_service import (
    MembershipConflictError,
    MembershipInvalidStateError,
    MembershipNotFoundError,
    MembershipUnauthorizedError,
    WorkspaceMembershipService,
)

logger = structlog.get_logger(__name__)

workspace_members_router = APIRouter(
    prefix="/workspaces/{workspace_id}/members",
    tags=["Workspace Members"],
)


@workspace_members_router.get(
    "",
    response_model=WorkspaceMemberListResponse,
    summary="List workspace members",
)
async def list_workspace_members(
    request: Request,
    workspace_id: uuid.UUID,
    search: str | None = Query(None, description="Search by username or email"),
    role: str | None = Query(None, description="Filter by role (e.g. OWNER, ADMIN, MEMBER, VIEWER)"),
    status_filter: str | None = Query(None, alias="status", description="Filter by status (ACTIVE, SUSPENDED)"),
    cursor: str | None = Query(None, description="Keyset cursor pagination"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: UserContext = Depends(get_current_user),
    service: WorkspaceMembershipService = Depends(get_workspace_membership_service),
    session: AsyncSession = Depends(get_db),
) -> WorkspaceMemberListResponse:
    """Lists workspace members with search, filters, and pagination.

    DEC-11: Platform Support permitted with mandatory ticket justification; Platform Auditor denied.
    """
    user_role = Role.from_str(str(current_user.role))
    is_diagnostic = False

    # 1. Deny Platform Auditor explicitly (DEC-11 policy boundary)
    if user_role == Role.PLATFORM_AUDITOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform auditor role is prohibited from accessing member lists.",
        )

    # 2. Platform Support: Ticket enforcement and fail-closed audit logging
    if user_role == Role.PLATFORM_SUPPORT:
        raw_ticket = request.headers.get("X-Justification-Ticket-ID")
        ticket_id = validate_diagnostic_ticket(raw_ticket)
        await record_diagnostic_access(
            session=session,
            user_id=current_user.id,
            user_role=user_role.value,
            action="DIAGNOSTIC_MEMBER_LIST_READ",
            resource_type="workspace_members",
            resource_id=str(workspace_id),
            ticket_id=ticket_id,
            tenant_id=workspace_id,
        )
        is_diagnostic = True

    try:
        skip = (page - 1) * page_size
        items, total, next_cursor = await service.list_members(
            workspace_id=workspace_id,
            actor_id=current_user.user_id,
            search=search,
            role=role,
            status=status_filter,
            cursor=cursor,
            skip=skip,
            limit=page_size,
            is_diagnostic=is_diagnostic,
        )
        return WorkspaceMemberListResponse(
            success=True,
            total=total,
            page=page,
            page_size=page_size,
            next_cursor=next_cursor,
            items=[WorkspaceMemberData.model_validate(m) for m in items],
        )
    except MembershipUnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error listing workspace members", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while listing workspace members.",
        )


@workspace_members_router.get(
    "/{member_id}",
    response_model=WorkspaceMemberResponse,
    summary="Get single workspace member profile",
)
async def get_workspace_member(
    workspace_id: uuid.UUID,
    member_id: uuid.UUID,
    current_user: UserContext = Depends(get_current_user),
    service: WorkspaceMembershipService = Depends(get_workspace_membership_service),
) -> WorkspaceMemberResponse:
    """Fetch details of a single workspace member."""
    try:
        member = await service.get_member(
            workspace_id=workspace_id,
            member_id=member_id,
            actor_id=current_user.user_id,
        )
        return WorkspaceMemberResponse(
            success=True,
            message="Workspace member retrieved successfully.",
            data=WorkspaceMemberData.model_validate(member),
        )
    except MembershipNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except MembershipUnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error fetching workspace member", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving the workspace member.",
        )


@workspace_members_router.patch(
    "/{member_id}/role",
    response_model=WorkspaceMemberResponse,
    summary="Update workspace member role",
)
async def update_workspace_member_role(
    workspace_id: uuid.UUID,
    member_id: uuid.UUID,
    payload: dict = Body(...),
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    service: WorkspaceMembershipService = Depends(get_workspace_membership_service),
) -> WorkspaceMemberResponse:
    """Updates a member's role with Last Owner Protection and hierarchy validation."""
    if isinstance(payload, dict) and payload.get("role") == "OWNER":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Direct assignment or promotion to OWNER is not permitted.",
        )
    try:
        request = UpdateMemberRoleRequest.model_validate(payload)
    except ValidationError as e:
        raise RequestValidationError(e.errors())

    try:
        member = await service.update_member_role(
            session=session,
            workspace_id=workspace_id,
            actor_id=current_user.user_id,
            member_id=member_id,
            new_role=request.role,
            dry_run=request.dry_run,
        )
        return WorkspaceMemberResponse(
            success=True,
            message="Workspace member role updated successfully.",
            data=WorkspaceMemberData.model_validate(member),
        )
    except MembershipNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except MembershipUnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except MembershipConflictError as e:
        detail_msg = str(e)
        if "leave as owner" in detail_msg.lower() or "last remaining owner" in detail_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "CANNOT_LEAVE_AS_OWNER",
                    "message": "Workspace owners cannot leave the workspace. You must transfer workspace ownership to another member before departing.",
                },
            )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail_msg)
    except MembershipInvalidStateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error updating member role", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating member role.",
        )


@workspace_members_router.post(
    "/{member_id}/suspend",
    response_model=WorkspaceMemberResponse,
    summary="Suspend a workspace member",
)
async def suspend_workspace_member(
    workspace_id: uuid.UUID,
    member_id: uuid.UUID,
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    service: WorkspaceMembershipService = Depends(get_workspace_membership_service),
) -> WorkspaceMemberResponse:
    """Suspends a workspace member."""
    try:
        member = await service.suspend_member(
            session=session,
            workspace_id=workspace_id,
            actor_id=current_user.user_id,
            member_id=member_id,
        )
        return WorkspaceMemberResponse(
            success=True,
            message="Workspace member suspended successfully.",
            data=WorkspaceMemberData.model_validate(member),
        )
    except MembershipNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except MembershipUnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except MembershipConflictError as e:
        detail_msg = str(e)
        if "leave as owner" in detail_msg.lower() or "last remaining owner" in detail_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "CANNOT_LEAVE_AS_OWNER",
                    "message": "Workspace owners cannot leave the workspace. You must transfer workspace ownership to another member before departing.",
                },
            )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail_msg)
    except MembershipInvalidStateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error suspending member", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while suspending member.",
        )


@workspace_members_router.post(
    "/{member_id}/restore",
    response_model=WorkspaceMemberResponse,
    summary="Restore a suspended workspace member",
)
async def restore_workspace_member(
    workspace_id: uuid.UUID,
    member_id: uuid.UUID,
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    service: WorkspaceMembershipService = Depends(get_workspace_membership_service),
) -> WorkspaceMemberResponse:
    """Restores a suspended workspace member to active status."""
    try:
        member = await service.restore_member(
            session=session,
            workspace_id=workspace_id,
            actor_id=current_user.user_id,
            member_id=member_id,
        )
        return WorkspaceMemberResponse(
            success=True,
            message="Workspace member restored successfully.",
            data=WorkspaceMemberData.model_validate(member),
        )
    except MembershipNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except MembershipUnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except MembershipConflictError as e:
        detail_msg = str(e)
        if "leave as owner" in detail_msg.lower() or "last remaining owner" in detail_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "CANNOT_LEAVE_AS_OWNER",
                    "message": "Workspace owners cannot leave the workspace. You must transfer workspace ownership to another member before departing.",
                },
            )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail_msg)
    except MembershipInvalidStateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error restoring member", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while restoring member.",
        )


@workspace_members_router.delete(
    "/{member_id}",
    response_model=WorkspaceMemberResponse,
    summary="Remove a workspace member",
)
async def remove_workspace_member(
    workspace_id: uuid.UUID,
    member_id: uuid.UUID,
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    service: WorkspaceMembershipService = Depends(get_workspace_membership_service),
) -> WorkspaceMemberResponse:
    """Soft removes a workspace member with Last Owner Protection."""
    try:
        member = await service.remove_member(
            session=session,
            workspace_id=workspace_id,
            actor_id=current_user.user_id,
            member_id=member_id,
        )
        return WorkspaceMemberResponse(
            success=True,
            message="Workspace member removed successfully.",
            data=WorkspaceMemberData.model_validate(member),
        )
    except MembershipNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except MembershipUnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except MembershipConflictError as e:
        detail_msg = str(e)
        if "leave as owner" in detail_msg.lower() or "last remaining owner" in detail_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "CANNOT_LEAVE_AS_OWNER",
                    "message": "Workspace owners cannot leave the workspace. You must transfer workspace ownership to another member before departing.",
                },
            )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail_msg)
    except MembershipInvalidStateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error removing member", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while removing member.",
        )


@workspace_members_router.post(
    "/leave",
    response_model=WorkspaceMemberResponse,
    summary="Leave a workspace",
)
async def leave_workspace(
    workspace_id: uuid.UUID,
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    service: WorkspaceMembershipService = Depends(get_workspace_membership_service),
) -> WorkspaceMemberResponse:
    """Self-leave workflow for an authenticated user."""
    try:
        # First find the member id for the current user
        member = await service.member_repo.get_membership(workspace_id, current_user.user_id)
        if not member:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="You are not a member of this workspace.")

        removed_member = await service.remove_member(
            session=session,
            workspace_id=workspace_id,
            actor_id=current_user.user_id,
            member_id=member.id,
        )
        return WorkspaceMemberResponse(
            success=True,
            message="Successfully left the workspace.",
            data=WorkspaceMemberData.model_validate(removed_member),
        )
    except MembershipNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except MembershipUnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except MembershipConflictError as e:
        detail_msg = str(e)
        if "leave as owner" in detail_msg.lower() or "last remaining owner" in detail_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "CANNOT_LEAVE_AS_OWNER",
                    "message": "Workspace owners cannot leave the workspace. You must transfer workspace ownership to another member before departing.",
                },
            )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail_msg)
    except MembershipInvalidStateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        logger.exception("Unexpected error leaving workspace", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while leaving workspace.",
        )




@workspace_members_router.post(
    "/bulk",
    response_model=BulkMemberActionResponse,
    summary="Bulk manage workspace members",
)
async def bulk_manage_workspace_members(
    workspace_id: uuid.UUID,
    request: BulkMemberActionRequest,
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    service: WorkspaceMembershipService = Depends(get_workspace_membership_service),
) -> BulkMemberActionResponse:
    """Executes a batch action across multiple members."""
    try:
        result = await service.bulk_update_members(
            session=session,
            workspace_id=workspace_id,
            actor_id=current_user.user_id,
            member_ids=request.member_ids,
            action=request.action,
            role=request.role,
        )
        return BulkMemberActionResponse(
            success=True,
            message="Bulk operation completed.",
            total=result["total"],
            results=[BulkMemberActionResult(**r) for r in result["results"]],
        )
    except MembershipUnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error executing bulk member action", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while executing bulk member action.",
        )
