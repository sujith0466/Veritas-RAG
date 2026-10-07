"""Workspace Access Requests API Endpoints.

Provides endpoints for submitting, listing, approving, and rejecting workspace access requests.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.api.v1.schemas.workspace_access_request import (
    AccessRequestData,
    AccessRequestListResponse,
    AccessRequestResponse,
    CreateAccessRequest,
    RejectAccessRequest,
)
from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import (
    get_access_request_service,
    get_db,
)
from backend.services.workspace.access_request_service import (
    AccessRequestConflictError,
    AccessRequestError,
    AccessRequestInvalidStateError,
    AccessRequestNotFoundError,
    AccessRequestService,
    AccessRequestUnauthorizedError,
)

logger = structlog.get_logger(__name__)

workspace_access_requests_router = APIRouter(
    prefix="/workspaces/{workspace_id}/access-requests",
    tags=["Workspace Access Requests"],
)


def _to_request_data(req) -> AccessRequestData:
    user_email = None
    user_display_name = None
    if getattr(req, "user", None):
        user_email = req.user.email
        user_display_name = req.user.display_name or req.user.username

    return AccessRequestData(
        id=req.id,
        workspace_id=req.workspace_id,
        user_id=req.user_id,
        request_type=req.request_type,
        current_role=req.current_role,
        requested_role=req.requested_role,
        status=req.status,
        reason=req.reason,
        reviewed_by_id=req.reviewed_by_id,
        reviewed_at=req.reviewed_at,
        rejection_reason=req.rejection_reason,
        created_at=req.created_at,
        user_email=user_email,
        user_display_name=user_display_name,
    )


@workspace_access_requests_router.post(
    "",
    response_model=AccessRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit access request",
)
async def create_access_request(
    workspace_id: uuid.UUID,
    payload: CreateAccessRequest,
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    service: AccessRequestService = Depends(get_access_request_service),
):
    """Submits a new role elevation or join approval request for the target workspace."""
    try:
        req = await service.create_request(
            session=session,
            workspace_id=workspace_id,
            actor_id=current_user.id,
            request_type=payload.request_type,
            requested_role=payload.requested_role,
            reason=payload.reason,
        )
        return AccessRequestResponse(success=True, request=_to_request_data(req))
    except AccessRequestConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except AccessRequestUnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except (AccessRequestNotFoundError, AccessRequestInvalidStateError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("Failed to create access request", error=str(e), exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to submit access request.")


@workspace_access_requests_router.get(
    "",
    response_model=AccessRequestListResponse,
    summary="List workspace access requests",
)
async def list_access_requests(
    workspace_id: uuid.UUID,
    status_filter: str | None = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: UserContext = Depends(get_current_user),
    service: AccessRequestService = Depends(get_access_request_service),
):
    """Lists access requests for a workspace. Requires OWNER or ADMIN privileges."""
    try:
        items, total = await service.list_requests(
            workspace_id=workspace_id,
            actor_id=current_user.id,
            status=status_filter,
            skip=skip,
            limit=limit,
        )
        return AccessRequestListResponse(
            items=[_to_request_data(item) for item in items],
            total=total,
            skip=skip,
            limit=limit,
        )
    except AccessRequestUnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.error("Failed to list access requests", error=str(e), exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list access requests.")


@workspace_access_requests_router.post(
    "/{request_id}/approve",
    response_model=AccessRequestResponse,
    summary="Approve access request",
)
async def approve_access_request(
    workspace_id: uuid.UUID,
    request_id: uuid.UUID,
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    service: AccessRequestService = Depends(get_access_request_service),
):
    """Approves an access request under an ACID row lock, transitioning membership and emitting AuditLog."""
    try:
        req = await service.approve_request(
            session=session,
            workspace_id=workspace_id,
            actor_id=current_user.id,
            request_id=request_id,
        )
        return AccessRequestResponse(success=True, request=_to_request_data(req))
    except AccessRequestNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except AccessRequestUnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except AccessRequestConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except AccessRequestInvalidStateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error("Failed to approve access request", error=str(e), exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to approve access request.")


@workspace_access_requests_router.post(
    "/{request_id}/reject",
    response_model=AccessRequestResponse,
    summary="Reject access request",
)
async def reject_access_request(
    workspace_id: uuid.UUID,
    request_id: uuid.UUID,
    payload: RejectAccessRequest | None = None,
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    service: AccessRequestService = Depends(get_access_request_service),
):
    """Rejects an access request and records rejection reason in AuditLog."""
    try:
        rejection_reason = payload.rejection_reason if payload else None
        req = await service.reject_request(
            session=session,
            workspace_id=workspace_id,
            actor_id=current_user.id,
            request_id=request_id,
            rejection_reason=rejection_reason,
        )
        return AccessRequestResponse(success=True, request=_to_request_data(req))
    except AccessRequestNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except AccessRequestUnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except AccessRequestConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        logger.error("Failed to reject access request", error=str(e), exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to reject access request.")
