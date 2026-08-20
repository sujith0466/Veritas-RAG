"""Workspace Invitations API Endpoints.

Provides endpoints for sending, listing, resending, revoking, and verifying invitations.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.api.v1.schemas.workspace_invitation import (
    AcceptInvitationData,
    AcceptInvitationRequest,
    AcceptInvitationResponse,
    ResendInvitationRequest,
    SendInvitationRequest,
    VerifyInvitationData,
    VerifyInvitationResponse,
    WorkspaceInvitationData,
    WorkspaceInvitationListResponse,
    WorkspaceInvitationResponse,
)
from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import (
    get_db,
    get_workspace_invitation_service,
)
from backend.services.workspace.invitation_service import (
    InvitationConflictError,
    InvitationError,
    InvitationInvalidStateError,
    InvitationNotFoundError,
    InvitationRateLimitError,
    InvitationUnauthorizedError,
    WorkspaceInvitationService,
)

logger = structlog.get_logger(__name__)

# Workspace-scoped invitation routes
workspace_invitations_router = APIRouter(
    prefix="/workspaces/{workspace_id}/invitations",
    tags=["Workspace Invitations"],
)

# Global invitation verification and acceptance routes
invitations_router = APIRouter(
    prefix="/invitations",
    tags=["Invitations"],
)


@workspace_invitations_router.post(
    "",
    response_model=WorkspaceInvitationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Send a workspace invitation",
)
async def send_workspace_invitation(
    workspace_id: uuid.UUID,
    request: SendInvitationRequest,
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    service: WorkspaceInvitationService = Depends(get_workspace_invitation_service),
) -> WorkspaceInvitationResponse:
    """Creates a new cryptographically secured workspace invitation and dispatches magic link."""
    try:
        invitation = await service.send_invitation(
            session=session,
            workspace_id=workspace_id,
            actor_id=current_user.user_id,
            email=request.email,
            role=request.role,
            custom_message=request.custom_message,
        )
        return WorkspaceInvitationResponse(
            success=True,
            message="Workspace invitation sent successfully.",
            data=WorkspaceInvitationData.model_validate(invitation),
        )
    except InvitationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvitationUnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except InvitationConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except InvitationRateLimitError as e:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))
    except InvitationInvalidStateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error sending workspace invitation", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating the workspace invitation.",
        )


@workspace_invitations_router.get(
    "",
    response_model=WorkspaceInvitationListResponse,
    summary="List workspace invitations",
)
async def list_workspace_invitations(
    workspace_id: uuid.UUID,
    status_filter: str | None = Query(None, alias="status", description="Filter by status (e.g. PENDING)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: UserContext = Depends(get_current_user),
    service: WorkspaceInvitationService = Depends(get_workspace_invitation_service),
) -> WorkspaceInvitationListResponse:
    """Lists invitations for the specified workspace with pagination."""
    try:
        skip = (page - 1) * page_size
        items, total = await service.list_invitations(
            workspace_id=workspace_id,
            actor_id=current_user.user_id,
            status=status_filter,
            skip=skip,
            limit=page_size,
        )
        return WorkspaceInvitationListResponse(
            success=True,
            total=total,
            page=page,
            page_size=page_size,
            items=[WorkspaceInvitationData.model_validate(inv) for inv in items],
        )
    except InvitationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvitationUnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error listing workspace invitations", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while listing workspace invitations.",
        )


@workspace_invitations_router.post(
    "/{invitation_id}/resend",
    response_model=WorkspaceInvitationResponse,
    summary="Resend a workspace invitation",
)
async def resend_workspace_invitation(
    workspace_id: uuid.UUID,
    invitation_id: uuid.UUID,
    request: ResendInvitationRequest | None = None,
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    service: WorkspaceInvitationService = Depends(get_workspace_invitation_service),
) -> WorkspaceInvitationResponse:
    """Rotates invitation token, extends expiration, and resends magic link."""
    try:
        custom_message = request.custom_message if request else None
        invitation = await service.resend_invitation(
            session=session,
            workspace_id=workspace_id,
            invitation_id=invitation_id,
            actor_id=current_user.user_id,
            custom_message=custom_message,
        )
        return WorkspaceInvitationResponse(
            success=True,
            message="Workspace invitation resent successfully.",
            data=WorkspaceInvitationData.model_validate(invitation),
        )
    except InvitationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvitationUnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except InvitationRateLimitError as e:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))
    except InvitationInvalidStateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error resending workspace invitation", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while resending the workspace invitation.",
        )


@workspace_invitations_router.delete(
    "/{invitation_id}",
    response_model=WorkspaceInvitationResponse,
    summary="Revoke a workspace invitation",
)
async def revoke_workspace_invitation(
    workspace_id: uuid.UUID,
    invitation_id: uuid.UUID,
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    service: WorkspaceInvitationService = Depends(get_workspace_invitation_service),
) -> WorkspaceInvitationResponse:
    """Revokes a pending workspace invitation."""
    try:
        invitation = await service.revoke_invitation(
            session=session,
            workspace_id=workspace_id,
            invitation_id=invitation_id,
            actor_id=current_user.user_id,
        )
        return WorkspaceInvitationResponse(
            success=True,
            message="Workspace invitation revoked successfully.",
            data=WorkspaceInvitationData.model_validate(invitation),
        )
    except InvitationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvitationUnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except InvitationInvalidStateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error revoking workspace invitation", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while revoking the workspace invitation.",
        )


# ── Standalone Public / Verification Endpoints ─────────────────────────────────

@invitations_router.get(
    "/verify",
    response_model=VerifyInvitationResponse,
    summary="Verify invitation token metadata",
)
async def verify_invitation_token(
    token: str = Query(..., description="Raw invitation token from email magic link"),
    session: AsyncSession = Depends(get_db),
    service: WorkspaceInvitationService = Depends(get_workspace_invitation_service),
) -> VerifyInvitationResponse:
    """Verifies token validity and returns metadata for the acceptance preview page."""
    try:
        data = await service.verify_invitation_token(session=session, raw_token=token)
        return VerifyInvitationResponse(
            success=True,
            message="Invitation token is valid.",
            data=VerifyInvitationData(**data),
        )
    except InvitationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvitationInvalidStateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error verifying invitation token", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while verifying the invitation token.",
        )


@invitations_router.post(
    "/accept",
    response_model=AcceptInvitationResponse,
    summary="Accept a workspace invitation",
)
async def accept_workspace_invitation(
    request: AcceptInvitationRequest,
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    service: WorkspaceInvitationService = Depends(get_workspace_invitation_service),
) -> AcceptInvitationResponse:
    """Accepts a pending workspace invitation, verifying identity and creating membership."""
    try:
        result = await service.accept_invitation(
            session=session,
            raw_token=request.token,
            user_context=current_user,
        )
        return AcceptInvitationResponse(
            success=True,
            message="Workspace invitation accepted successfully.",
            data=AcceptInvitationData(**result),
        )
    except InvitationNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvitationUnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except InvitationConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except InvitationInvalidStateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except InvitationError as e:
        # AUTH-010: base InvitationError (e.g. empty token) must return 400, not 500
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error accepting workspace invitation", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while accepting the workspace invitation.",
        )
