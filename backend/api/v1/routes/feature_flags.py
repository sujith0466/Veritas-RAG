"""Feature Flag API Endpoints.

Provides administrative lifecycle management, emergency killswitches,
workspace override rules, and real-time flag evaluation.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.api.v1.schemas.feature_flag import (
    FeatureFlagBulkEvaluationResponse,
    FeatureFlagCreateRequest,
    FeatureFlagDataResponse,
    FeatureFlagEvaluationDataResponse,
    FeatureFlagEvaluationResponse,
    FeatureFlagHistoryDataResponse,
    FeatureFlagHistoryResponse,
    FeatureFlagKillswitchRequest,
    FeatureFlagListResponse,
    FeatureFlagResponse,
    FeatureFlagUpdateRequest,
    FeatureFlagWorkspaceRuleDataResponse,
    FeatureFlagWorkspaceRuleRequest,
    FeatureFlagWorkspaceRuleResponse,
)
from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user, require_role
from backend.core.dependencies.database import (
    get_db,
    get_feature_flag_evaluation_service,
    get_feature_flag_management_service,
    get_feature_flag_repository,
    get_workspace_member_repository,
)
from backend.core.permissions.rbac import Role
from backend.repositories.feature_flag import FeatureFlagRepository
from backend.repositories.workspace_member import WorkspaceMemberRepository
from backend.services.feature_flag.evaluation_service import (
    EvaluationContext,
    FeatureFlagEvaluationService,
)
from backend.services.feature_flag.management_service import (
    FeatureFlagManagementService,
)
from backend.services.workspace.management_service import (
    WorkspaceUnauthorizedError,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/feature-flags", tags=["Feature Flags"])
workspace_ff_router = APIRouter(prefix="/workspaces/{workspace_id}/feature-flags", tags=["Workspace Feature Flags"])


# ── 1. Master Flag Management Endpoints ──────────────────────────────────────

@router.post(
    "",
    response_model=FeatureFlagResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create master feature flag (Platform Admin only)",
    dependencies=[Depends(require_role([Role.ADMIN]))],
)
async def create_feature_flag(
    request: FeatureFlagCreateRequest,
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    management_service: FeatureFlagManagementService = Depends(get_feature_flag_management_service),
) -> FeatureFlagResponse:
    """Create a new master feature flag."""
    try:
        flag = await management_service.create_flag(
            session=session,
            actor_id=current_user.id,
            key=request.key,
            name=request.name,
            description=request.description,
            category=request.category,
            lifecycle_state=request.lifecycle_state,
            flag_type=request.flag_type,
            default_enabled=request.default_enabled,
            prerequisite_flag_keys=request.prerequisite_flag_keys,
            default_variant_json=request.default_variant,
            target_environments=request.target_environments,
            change_reason=request.change_reason,
        )
        return FeatureFlagResponse(
            success=True,
            data=FeatureFlagDataResponse(
                id=flag.id,
                key=flag.key,
                name=flag.name,
                description=flag.description,
                category=flag.category,
                lifecycle_state=flag.lifecycle_state,
                flag_type=flag.flag_type,
                default_enabled=flag.default_enabled,
                is_killswitch_active=flag.is_killswitch_active,
                prerequisite_flag_keys=flag.prerequisite_flag_keys,
                default_variant=flag.default_variant_json,
                target_environments=flag.target_environments.split(","),
                version=flag.version,
                created_at=flag.created_at,
                updated_at=flag.updated_at,
            ),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Failed to create feature flag")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating feature flag.",
        ) from e


@router.get(
    "",
    response_model=FeatureFlagListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all active feature flags",
)
async def list_feature_flags(
    category: str | None = Query(None, description="Filter by category"),
    flag_repo: FeatureFlagRepository = Depends(get_feature_flag_repository),
    current_user: UserContext = Depends(get_current_user),
) -> FeatureFlagListResponse:
    """List all active master feature flags."""
    try:
        flags = await flag_repo.list_active_flags(category=category)
        return FeatureFlagListResponse(
            success=True,
            data=[
                FeatureFlagDataResponse(
                    id=f.id,
                    key=f.key,
                    name=f.name,
                    description=f.description,
                    category=f.category,
                    lifecycle_state=f.lifecycle_state,
                    flag_type=f.flag_type,
                    default_enabled=f.default_enabled,
                    is_killswitch_active=f.is_killswitch_active,
                    prerequisite_flag_keys=f.prerequisite_flag_keys,
                    default_variant=f.default_variant_json,
                    target_environments=f.target_environments.split(","),
                    version=f.version,
                    created_at=f.created_at,
                    updated_at=f.updated_at,
                )
                for f in flags
            ],
        )
    except Exception as e:
        logger.exception("Failed to list feature flags")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while listing feature flags.",
        ) from e


@router.get(
    "/{flag_key}",
    response_model=FeatureFlagResponse,
    status_code=status.HTTP_200_OK,
    summary="Get feature flag details",
)
async def get_feature_flag(
    flag_key: str,
    flag_repo: FeatureFlagRepository = Depends(get_feature_flag_repository),
    current_user: UserContext = Depends(get_current_user),
) -> FeatureFlagResponse:
    """Get details of a specific feature flag."""
    flag = await flag_repo.get_by_key(flag_key)
    if not flag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Feature flag '{flag_key}' not found.")

    return FeatureFlagResponse(
        success=True,
        data=FeatureFlagDataResponse(
            id=flag.id,
            key=flag.key,
            name=flag.name,
            description=flag.description,
            category=flag.category,
            lifecycle_state=flag.lifecycle_state,
            flag_type=flag.flag_type,
            default_enabled=flag.default_enabled,
            is_killswitch_active=flag.is_killswitch_active,
            prerequisite_flag_keys=flag.prerequisite_flag_keys,
            default_variant=flag.default_variant_json,
            target_environments=flag.target_environments.split(","),
            version=flag.version,
            created_at=flag.created_at,
            updated_at=flag.updated_at,
        ),
    )


@router.patch(
    "/{flag_key}",
    response_model=FeatureFlagResponse,
    status_code=status.HTTP_200_OK,
    summary="Update feature flag (Platform Admin only)",
    dependencies=[Depends(require_role([Role.ADMIN]))],
)
async def update_feature_flag(
    flag_key: str,
    request: FeatureFlagUpdateRequest,
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    management_service: FeatureFlagManagementService = Depends(get_feature_flag_management_service),
) -> FeatureFlagResponse:
    """Update master feature flag configuration."""
    try:
        flag = await management_service.update_flag(
            session=session,
            actor_id=current_user.id,
            key=flag_key,
            name=request.name,
            description=request.description,
            category=request.category,
            lifecycle_state=request.lifecycle_state,
            default_enabled=request.default_enabled,
            prerequisite_flag_keys=request.prerequisite_flag_keys,
            default_variant_json=request.default_variant,
            target_environments=request.target_environments,
            change_reason=request.change_reason,
        )
        return FeatureFlagResponse(
            success=True,
            data=FeatureFlagDataResponse(
                id=flag.id,
                key=flag.key,
                name=flag.name,
                description=flag.description,
                category=flag.category,
                lifecycle_state=flag.lifecycle_state,
                flag_type=flag.flag_type,
                default_enabled=flag.default_enabled,
                is_killswitch_active=flag.is_killswitch_active,
                prerequisite_flag_keys=flag.prerequisite_flag_keys,
                default_variant=flag.default_variant_json,
                target_environments=flag.target_environments.split(","),
                version=flag.version,
                created_at=flag.created_at,
                updated_at=flag.updated_at,
            ),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Failed to update feature flag")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while updating feature flag.",
        ) from e


@router.post(
    "/{flag_key}/killswitch",
    response_model=FeatureFlagResponse,
    status_code=status.HTTP_200_OK,
    summary="Toggle emergency killswitch (Platform Admin only)",
    dependencies=[Depends(require_role([Role.ADMIN]))],
)
async def toggle_killswitch(
    flag_key: str,
    request: FeatureFlagKillswitchRequest,
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    management_service: FeatureFlagManagementService = Depends(get_feature_flag_management_service),
) -> FeatureFlagResponse:
    """Instantly engage or disengage emergency kill switch."""
    try:
        flag = await management_service.toggle_killswitch(
            session=session,
            actor_id=current_user.id,
            key=flag_key,
            is_active=request.is_active,
            reason=request.reason,
        )
        return FeatureFlagResponse(
            success=True,
            data=FeatureFlagDataResponse(
                id=flag.id,
                key=flag.key,
                name=flag.name,
                description=flag.description,
                category=flag.category,
                lifecycle_state=flag.lifecycle_state,
                flag_type=flag.flag_type,
                default_enabled=flag.default_enabled,
                is_killswitch_active=flag.is_killswitch_active,
                prerequisite_flag_keys=flag.prerequisite_flag_keys,
                default_variant=flag.default_variant_json,
                target_environments=flag.target_environments.split(","),
                version=flag.version,
                created_at=flag.created_at,
                updated_at=flag.updated_at,
            ),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.exception("Failed to toggle kill switch")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while toggling kill switch.",
        ) from e


@router.get(
    "/{flag_key}/history",
    response_model=FeatureFlagHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get feature flag audit history (Platform Admin only)",
    dependencies=[Depends(require_role([Role.ADMIN]))],
)
async def get_flag_history(
    flag_key: str,
    limit: int = Query(50, ge=1, le=100),
    management_service: FeatureFlagManagementService = Depends(get_feature_flag_management_service),
    current_user: UserContext = Depends(get_current_user),
) -> FeatureFlagHistoryResponse:
    """Fetch audit history log for a feature flag."""
    try:
        history = await management_service.get_history(flag_key=flag_key, limit=limit)
        return FeatureFlagHistoryResponse(
            success=True,
            data=[
                FeatureFlagHistoryDataResponse(
                    id=h.id,
                    flag_id=h.flag_id,
                    workspace_id=h.workspace_id,
                    changed_by_user_id=h.changed_by_user_id,
                    version=h.version,
                    change_action=h.change_action,
                    change_reason=h.change_reason,
                    old_rule=h.old_rule_json,
                    new_rule=h.new_rule_json,
                    created_at=h.created_at,
                )
                for h in history
            ],
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.exception("Failed to fetch flag history")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while fetching flag history.",
        ) from e


# ── 2. Workspace Feature Flag Endpoints ──────────────────────────────────────

@workspace_ff_router.get(
    "",
    response_model=FeatureFlagBulkEvaluationResponse,
    status_code=status.HTTP_200_OK,
    summary="Evaluate all feature flags for a workspace",
)
async def evaluate_workspace_feature_flags(
    workspace_id: uuid.UUID,
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    evaluation_service: FeatureFlagEvaluationService = Depends(get_feature_flag_evaluation_service),
    member_repo: WorkspaceMemberRepository = Depends(get_workspace_member_repository),
) -> FeatureFlagBulkEvaluationResponse:
    """Evaluate all feature flags for the calling user in the specified workspace context."""
    # Check membership unless platform admin
    workspace_role = None
    if current_user.role != Role.ADMIN:
        membership = await member_repo.get_membership(workspace_id, current_user.id)
        if not membership:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found or access denied.")
        workspace_role = membership.role

    context = EvaluationContext(
        workspace_id=workspace_id,
        user_id=current_user.id,
        user_email=current_user.email,
        workspace_role=workspace_role,
    )

    evaluations = await evaluation_service.evaluate_all_flags_for_workspace(
        session=session,
        context=context,
    )

    return FeatureFlagBulkEvaluationResponse(
        success=True,
        workspace_id=workspace_id,
        flags={
            k: FeatureFlagEvaluationDataResponse(
                flag_key=v.flag_key,
                is_enabled=v.is_enabled,
                variant=v.variant,
                reason=v.reason,
                tier_served=v.tier_served,
                evaluated_at=v.evaluated_at,
            )
            for k, v in evaluations.items()
        },
    )


@workspace_ff_router.get(
    "/{flag_key}/evaluate",
    response_model=FeatureFlagEvaluationResponse,
    status_code=status.HTTP_200_OK,
    summary="Evaluate a single feature flag for a workspace",
)
async def evaluate_single_feature_flag(
    workspace_id: uuid.UUID,
    flag_key: str,
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    evaluation_service: FeatureFlagEvaluationService = Depends(get_feature_flag_evaluation_service),
    member_repo: WorkspaceMemberRepository = Depends(get_workspace_member_repository),
) -> FeatureFlagEvaluationResponse:
    """Evaluate a specific feature flag with deterministic 7-step priority pipeline."""
    workspace_role = None
    if current_user.role != Role.ADMIN:
        membership = await member_repo.get_membership(workspace_id, current_user.id)
        if not membership:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found or access denied.")
        workspace_role = membership.role

    context = EvaluationContext(
        workspace_id=workspace_id,
        user_id=current_user.id,
        user_email=current_user.email,
        workspace_role=workspace_role,
    )

    result = await evaluation_service.evaluate_flag(
        session=session,
        flag_key=flag_key,
        context=context,
    )

    return FeatureFlagEvaluationResponse(
        success=True,
        data=FeatureFlagEvaluationDataResponse(
            flag_key=result.flag_key,
            is_enabled=result.is_enabled,
            variant=result.variant,
            reason=result.reason,
            tier_served=result.tier_served,
            evaluated_at=result.evaluated_at,
        ),
    )


@workspace_ff_router.put(
    "/{flag_key}",
    response_model=FeatureFlagWorkspaceRuleResponse,
    status_code=status.HTTP_200_OK,
    summary="Set workspace override rule for feature flag (Workspace Admin/Owner)",
)
async def set_workspace_feature_flag_rule(
    workspace_id: uuid.UUID,
    flag_key: str,
    request: FeatureFlagWorkspaceRuleRequest,
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    management_service: FeatureFlagManagementService = Depends(get_feature_flag_management_service),
) -> FeatureFlagWorkspaceRuleResponse:
    """Configure or update workspace-specific override rule for a flag."""
    try:
        is_platform_admin = current_user.role == Role.ADMIN
        rule = await management_service.set_workspace_rule(
            session=session,
            workspace_id=workspace_id,
            actor_id=current_user.id,
            key=flag_key,
            is_enabled=request.is_enabled,
            rollout_percentage=request.rollout_percentage,
            activation_start_at=request.activation_start_at,
            activation_end_at=request.activation_end_at,
            targeting_conditions=request.targeting_conditions,
            custom_variant=request.custom_variant,
            change_reason=request.change_reason,
            is_platform_admin=is_platform_admin,
        )
        return FeatureFlagWorkspaceRuleResponse(
            success=True,
            data=FeatureFlagWorkspaceRuleDataResponse(
                id=rule.id,
                flag_id=rule.flag_id,
                workspace_id=rule.workspace_id,
                is_enabled=rule.is_enabled,
                rollout_percentage=rule.rollout_percentage,
                activation_start_at=rule.activation_start_at,
                activation_end_at=rule.activation_end_at,
                targeting_conditions=rule.targeting_conditions_json,
                custom_variant=rule.custom_variant_json,
                version=rule.version,
                created_at=rule.created_at,
                updated_at=rule.updated_at,
            ),
        )
    except WorkspaceUnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("Failed to set workspace feature flag rule")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while configuring feature flag rule.",
        ) from e


@workspace_ff_router.delete(
    "/{flag_key}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete workspace override rule (Workspace Admin/Owner)",
)
async def delete_workspace_feature_flag_rule(
    workspace_id: uuid.UUID,
    flag_key: str,
    current_user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    management_service: FeatureFlagManagementService = Depends(get_feature_flag_management_service),
) -> None:
    """Delete workspace override rule and revert back to global default behavior."""
    try:
        is_platform_admin = current_user.role == Role.ADMIN
        await management_service.delete_workspace_rule(
            session=session,
            workspace_id=workspace_id,
            actor_id=current_user.id,
            key=flag_key,
            is_platform_admin=is_platform_admin,
        )
    except WorkspaceUnauthorizedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.exception("Failed to delete workspace feature flag rule")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while deleting feature flag rule.",
        ) from e
