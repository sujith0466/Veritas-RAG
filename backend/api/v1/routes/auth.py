"""Authentication and user profile inspection routes.

Provides endpoints for inspecting current authentication state (`/status`)
and retrieving authenticated user profiles (`/me`).
"""

import uuid

from fastapi import APIRouter, Depends, Request
import structlog

from backend.api.v1.schemas.auth import AuthStatusResponse, UserContext
from backend.api.v1.schemas.common import ResponseMetadata, SuccessResponse
from backend.core.dependencies.auth import get_current_user, get_optional_user

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


def _build_metadata(request: Request) -> ResponseMetadata:
    """Helper to construct standard ResponseMetadata for envelopes."""
    req_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
    return ResponseMetadata(request_id=req_id)


@router.get(
    "/me",
    response_model=SuccessResponse[UserContext],
    summary="Get current user profile",
    description="Returns the authenticated UserContext of the calling user.",
)
async def get_me(
    request: Request,
    user: UserContext = Depends(get_current_user),
) -> SuccessResponse[UserContext]:
    """Return the currently authenticated user profile."""
    return SuccessResponse(
        success=True,
        data=user,
        metadata=_build_metadata(request),
    )


@router.get(
    "/status",
    response_model=SuccessResponse[AuthStatusResponse],
    summary="Get authentication status",
    description="Returns whether the request is authenticated and optional user summary.",
)
async def get_status(
    request: Request,
    user: UserContext | None = Depends(get_optional_user),
) -> SuccessResponse[AuthStatusResponse]:
    """Inspect current authentication status without requiring a valid token."""
    return SuccessResponse(
        success=True,
        data=AuthStatusResponse(
            is_authenticated=user is not None,
            user=user,
        ),
        metadata=_build_metadata(request),
    )
