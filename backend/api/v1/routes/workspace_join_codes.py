"""Workspace Join Codes API Endpoints.

Provides endpoints for creator-scoped join-code generation, retrieval,
revocation, custodian claims, and redemption activity auditing.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.api.v1.schemas.workspace_join_code import (
    ClaimCustodianRequest,
    CreateJoinCodeRequest,
    MemberAccessStatusEnum,
    MemberJoinAccessResponse,
    WorkspaceJoinCodeActivityResponse,
    WorkspaceJoinCodeData,
    WorkspaceJoinCodeRedemptionData,
    WorkspaceJoinCodeResponse,
)
from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import (
    get_db,
    get_join_code_service,
)
from backend.services.workspace.join_code_service import JoinCodeService
from backend.services.workspace.management_service import (
    WorkspaceNotFoundError,
    WorkspaceUnauthorizedError,
)

logger = structlog.get_logger(__name__)

workspace_join_codes_router = APIRouter(
    prefix="/workspaces/{workspace_id}/join-codes",
    tags=["Workspace Join Codes"],
)


@workspace_join_codes_router.post(
    "",
    response_model=WorkspaceJoinCodeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or rotate my creator-scoped join code",
)
async def create_or_rotate_my_join_code(
    workspace_id: uuid.UUID,
    request: CreateJoinCodeRequest | None = None,
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    service: JoinCodeService = Depends(get_join_code_service),
) -> WorkspaceJoinCodeResponse:
    """Creates a new creator-scoped join code or rotates the current user's existing code."""
    try:
        expires_in = request.expires_in_days if request and request.expires_in_days else 7
        result = await service.generate_new_join_code(
            session=session,
            workspace_id=workspace_id,
            user_id=current_user.user_id,
            expires_in_days=expires_in,
        )
        return WorkspaceJoinCodeResponse(
            success=True,
            message="Workspace join code created successfully.",
            data=WorkspaceJoinCodeData(
                id=result.join_code_id or uuid.uuid4(),
                workspace_id=workspace_id,
                created_by_user_id=current_user.user_id,
                operational_custodian_user_id=None,
                expires_at=result.expires_at,
                is_active=True,
                use_count=0,
                created_at=result.expires_at,
                updated_at=result.expires_at,
            ),
            join_code=result.join_code,
        )
    except WorkspaceNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except WorkspaceUnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error creating join code", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating the join code.",
        )


@workspace_join_codes_router.get(
    "/member-access",
    response_model=MemberJoinAccessResponse,
    summary="Get join code credentials for member peer-sharing",
)
async def get_member_join_access(
    workspace_id: uuid.UUID,
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    service: JoinCodeService = Depends(get_join_code_service),
) -> MemberJoinAccessResponse:
    """Resolves originating creator's active join code for authenticated member peer sharing."""
    try:
        return await service.resolve_member_join_credentials(
            session=session,
            workspace_id=workspace_id,
            caller_id=current_user.user_id,
        )
    except WorkspaceNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except WorkspaceUnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error in member join access resolution", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while resolving member join access.",
        )


@workspace_join_codes_router.post(
    "/rotate",
    response_model=WorkspaceJoinCodeResponse,
    summary="Rotate my creator-scoped join code",
)
async def rotate_my_join_code(
    workspace_id: uuid.UUID,
    request: CreateJoinCodeRequest | None = None,
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    service: JoinCodeService = Depends(get_join_code_service),
) -> WorkspaceJoinCodeResponse:
    """Rotates creator's join code. Returns single-reveal plaintext upon rotation."""
    try:
        expires_in = request.expires_in_days if request and request.expires_in_days else 7
        result = await service.generate_new_join_code(
            session=session,
            workspace_id=workspace_id,
            user_id=current_user.user_id,
            expires_in_days=expires_in,
            is_regeneration=True,
        )
        return WorkspaceJoinCodeResponse(
            success=True,
            message="Workspace join code rotated successfully.",
            data=WorkspaceJoinCodeData(
                id=result.join_code_id or uuid.uuid4(),
                workspace_id=workspace_id,
                created_by_user_id=current_user.user_id,
                operational_custodian_user_id=None,
                expires_at=result.expires_at,
                is_active=True,
                code_display=result.code_display,
                use_count=0,
                created_at=result.expires_at,
                updated_at=result.expires_at,
            ),
            join_code=result.join_code,
        )
    except WorkspaceNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except WorkspaceUnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error rotating join code", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while rotating the join code.",
        )


@workspace_join_codes_router.get(
    "/mine",
    response_model=WorkspaceJoinCodeResponse,
    summary="Get my active join code settings (masked preview)",
)
@workspace_join_codes_router.get(
    "/me",
    response_model=WorkspaceJoinCodeResponse,
    summary="Get my active join code",
)
async def get_my_active_join_code(
    workspace_id: uuid.UUID,
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    service: JoinCodeService = Depends(get_join_code_service),
) -> WorkspaceJoinCodeResponse:
    """Retrieves the caller's currently active creator-scoped join code with masked preview under single-reveal policy."""
    try:
        code, _ = await service.get_creator_join_code(
            session=session,
            workspace_id=workspace_id,
            user_id=current_user.user_id,
        )
        if not code:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active join code found.")

        # Single-reveal invariant: GET endpoints never return plaintext
        return WorkspaceJoinCodeResponse(
            success=True,
            message="Active join code retrieved successfully.",
            data=WorkspaceJoinCodeData.model_validate(code),
            join_code=None,
        )
    except WorkspaceNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except WorkspaceUnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error retrieving active join code", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving the active join code.",
        )


@workspace_join_codes_router.delete(
    "/mine",
    response_model=WorkspaceJoinCodeResponse,
    summary="Revoke my active join code",
)
async def revoke_my_active_join_code(
    workspace_id: uuid.UUID,
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    service: JoinCodeService = Depends(get_join_code_service),
) -> WorkspaceJoinCodeResponse:
    """Revokes caller's active join code."""
    try:
        code = await service.join_code_repo.get_any_active_by_user(session, workspace_id, current_user.user_id)
        if not code:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active join code found to revoke.")
        revoked = await service.revoke_creator_join_code(
            session=session,
            workspace_id=workspace_id,
            code_id=code.id,
            actor_id=current_user.user_id,
        )
        return WorkspaceJoinCodeResponse(
            success=True,
            message="Workspace join code revoked successfully.",
            data=WorkspaceJoinCodeData.model_validate(revoked),
            join_code=None,
        )
    except WorkspaceNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except WorkspaceUnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error revoking active join code", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while revoking the join code.",
        )


@workspace_join_codes_router.post(
    "/{code_id}/claim-custodian",
    response_model=WorkspaceJoinCodeResponse,
    summary="Claim operational custodianship of an unmapped legacy join code",
)
async def claim_legacy_custodian(
    workspace_id: uuid.UUID,
    code_id: uuid.UUID,
    request: ClaimCustodianRequest | None = None,
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    service: JoinCodeService = Depends(get_join_code_service),
) -> WorkspaceJoinCodeResponse:
    """Allows an active workspace OWNER to claim operational custodianship of an unmapped legacy code."""
    try:
        code = await service.claim_legacy_join_code(
            session=session,
            workspace_id=workspace_id,
            claiming_owner_id=current_user.user_id,
            code_id=code_id,
        )
        return WorkspaceJoinCodeResponse(
            success=True,
            message="Operational custodianship claimed successfully.",
            data=WorkspaceJoinCodeData.model_validate(code),
        )
    except WorkspaceNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except WorkspaceUnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error claiming legacy join code custodianship", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while claiming custodianship.",
        )


@workspace_join_codes_router.get(
    "/activity",
    response_model=WorkspaceJoinCodeActivityResponse,
    summary="Get redemption activity for my join codes",
)
async def get_my_join_code_activity(
    workspace_id: uuid.UUID,
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    service: JoinCodeService = Depends(get_join_code_service),
) -> WorkspaceJoinCodeActivityResponse:
    """Retrieves the redemption activity log for codes created or managed by the caller."""
    try:
        redemptions = await service.list_creator_redemptions(
            session=session,
            workspace_id=workspace_id,
            creator_user_id=current_user.user_id,
        )
        return WorkspaceJoinCodeActivityResponse(
            success=True,
            total=len(redemptions),
            items=[WorkspaceJoinCodeRedemptionData.model_validate(r) for r in redemptions],
        )
    except WorkspaceNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except WorkspaceUnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error retrieving join code activity", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving join code activity.",
        )


@workspace_join_codes_router.delete(
    "/{code_id}",
    response_model=WorkspaceJoinCodeResponse,
    summary="Revoke my join code",
)
async def revoke_my_join_code(
    workspace_id: uuid.UUID,
    code_id: uuid.UUID,
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    service: JoinCodeService = Depends(get_join_code_service),
) -> WorkspaceJoinCodeResponse:
    """Revokes an active join code owned or custodied by the caller."""
    try:
        code = await service.revoke_creator_join_code(
            session=session,
            workspace_id=workspace_id,
            code_id=code_id,
            actor_id=current_user.user_id,
        )
        return WorkspaceJoinCodeResponse(
            success=True,
            message="Workspace join code revoked successfully.",
            data=WorkspaceJoinCodeData.model_validate(code),
        )
    except WorkspaceNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except WorkspaceUnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error revoking join code", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while revoking the join code.",
        )
