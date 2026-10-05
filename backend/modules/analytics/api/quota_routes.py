import datetime
from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import get_db as get_db_session
from backend.core.dependencies.rbac import require_role
from backend.core.dependencies.workspace import (
    get_workspace_member_or_raise,
    require_workspace_admin_or_owner,
)
from backend.core.permissions.rbac import Role
from backend.modules.analytics.models.tenant_quota import TenantQuotaORM
from backend.modules.analytics.repositories.quota_repository import QuotaRepository
from backend.modules.analytics.repositories.usage_repository import UsageRepository
from backend.modules.analytics.schemas.analytics_dto import (
    TenantQuotaDTO,
    TenantQuotaUpdateDTO,
    WorkspaceUsageDTO,
    WorkspaceUserQuotaDTO,
    WorkspaceUserQuotaUpdateDTO,
)
from backend.modules.analytics.services.quota import QuotaGovernor

router = APIRouter(prefix="/v1", tags=["Quota & Usage"])


@router.get("/quotas/{tenant_id}", response_model=TenantQuotaDTO)
async def get_quota(
    tenant_id: str,
    auth: Annotated[UserContext, Depends(require_role(Role.ADMIN, Role.OWNER, Role.PLATFORM_ADMIN))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Fetch quota settings and real-time remaining tokens."""
    # Canonical workspace authorization if tenant_id is a UUID
    ws_uuid = None
    try:
        ws_uuid = uuid.UUID(tenant_id)
    except (ValueError, TypeError):
        pass

    user_role = Role.from_str(auth.role) if isinstance(auth.role, str) else auth.role
    is_platform_admin = user_role == Role.PLATFORM_ADMIN

    if ws_uuid:
        if not is_platform_admin:
            member = await get_workspace_member_or_raise(ws_uuid, auth, session)
            member_role = (member.role or "").strip().upper() if member else ""
            if member_role not in ("OWNER", "ADMIN"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Forbidden: Requires workspace Admin or Owner role.",
                )
    elif auth.tenant_id != tenant_id and not is_platform_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot access quota of another tenant.")

    governor = QuotaGovernor()
    quota = await governor.get_quota_settings(workspace_id=ws_uuid, tenant_id=tenant_id, session=session)
    used_tokens = await governor.get_durable_usage(ws_uuid, session) if ws_uuid else 0
    remaining = max(0, quota.monthly_token_limit - used_tokens)

    return TenantQuotaDTO(
        tenant_id=tenant_id,
        monthly_token_limit=quota.monthly_token_limit,
        monthly_budget_usd=quota.monthly_budget_usd,
        warning_threshold_pct=quota.warning_threshold_pct,
        is_hard_enforced=quota.is_hard_enforced,
        remaining_tokens=remaining,
        remaining_budget_usd=quota.monthly_budget_usd * (remaining / max(1, quota.monthly_token_limit)),
    )


@router.put("/quotas/{tenant_id}", response_model=TenantQuotaDTO)
async def update_quota(
    tenant_id: str,
    req: TenantQuotaUpdateDTO,
    auth: Annotated[UserContext, Depends(require_role(Role.OWNER, Role.ADMIN, Role.PLATFORM_ADMIN))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Update quota limits (OWNER, ADMIN, or PLATFORM_ADMIN)."""
    ws_uuid = None
    try:
        ws_uuid = uuid.UUID(tenant_id)
    except (ValueError, TypeError):
        pass

    user_role = Role.from_str(auth.role) if isinstance(auth.role, str) else auth.role
    is_platform_admin = user_role == Role.PLATFORM_ADMIN

    if ws_uuid:
        if not is_platform_admin:
            member = await get_workspace_member_or_raise(ws_uuid, auth, session)
            member_role = (member.role or "").strip().upper() if member else ""
            if member_role not in ("OWNER", "ADMIN"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Forbidden: Requires workspace Owner or Admin role to update quotas.",
                )
    elif auth.tenant_id != tenant_id and not is_platform_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot update quota of another tenant.")

    repo = QuotaRepository(session)
    quota = await repo.get_by_tenant_id(tenant_id)
    current_limit = quota.monthly_token_limit if quota else 10_000_000

    new_limit = req.monthly_token_limit if req.monthly_token_limit is not None else current_limit
    new_budget = req.monthly_budget_usd if req.monthly_budget_usd is not None else (quota.monthly_budget_usd if quota else 150.0)
    new_warning = req.warning_threshold_pct if req.warning_threshold_pct is not None else (quota.warning_threshold_pct if quota else 0.80)
    new_enforced = req.is_hard_enforced if req.is_hard_enforced is not None else (quota.is_hard_enforced if quota else True)

    updated_quota = await repo.create_or_update(
        tenant_id=tenant_id,
        monthly_token_limit=new_limit,
        monthly_budget_usd=new_budget,
        warning_threshold_pct=new_warning,
        is_hard_enforced=new_enforced,
    )
    if ws_uuid and not updated_quota.workspace_id:
        updated_quota.workspace_id = ws_uuid
        await session.commit()

    # Synchronize canonical workspace_settings if present
    if ws_uuid:
        from backend.models.entities.workspace_settings import WorkspaceSettings
        stmt_ws = select(WorkspaceSettings).where(WorkspaceSettings.workspace_id == ws_uuid)
        res_ws = await session.execute(stmt_ws)
        ws_settings = res_ws.scalar_one_or_none()
        if ws_settings and ws_settings.settings_json:
            current_json = dict(ws_settings.settings_json)
            limits_json = dict(current_json.get("limits") or {})
            limits_json["monthly_token_budget"] = new_limit
            current_json["limits"] = limits_json
            ws_settings.settings_json = current_json
            ws_settings.version = (ws_settings.version or 1) + 1
            await session.commit()

    governor = QuotaGovernor()
    used_tokens = await governor.get_durable_usage(ws_uuid, session) if ws_uuid else 0
    remaining = max(0, updated_quota.monthly_token_limit - used_tokens)
    await governor.set_remaining_tokens(tenant_id, remaining)

    return TenantQuotaDTO(
        tenant_id=tenant_id,
        monthly_token_limit=updated_quota.monthly_token_limit,
        monthly_budget_usd=updated_quota.monthly_budget_usd,
        warning_threshold_pct=updated_quota.warning_threshold_pct,
        is_hard_enforced=updated_quota.is_hard_enforced,
        remaining_tokens=remaining,
        remaining_budget_usd=updated_quota.monthly_budget_usd * (remaining / max(1, updated_quota.monthly_token_limit)),
    )


@router.get("/workspace-usage/{workspace_id}", response_model=WorkspaceUsageDTO)
async def get_workspace_usage(
    workspace_id: uuid.UUID,
    auth: Annotated[
        UserContext,
        Depends(
            require_role(
                Role.OWNER,
                Role.ADMIN,
                Role.ANALYST,
                Role.PLATFORM_ADMIN,
                Role.PLATFORM_SUPPORT,
                Role.PLATFORM_AUDITOR,
            )
        ),
    ],
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Fetch real durable workspace token and query usage metrics."""
    await get_workspace_member_or_raise(workspace_id, auth, session)

    usage_repo = UsageRepository(session)
    period_start = usage_repo.get_current_period_start()
    usage = await usage_repo.get_current_period_usage(workspace_id, period_start)

    used_tokens = usage.used_tokens if usage else 0
    used_queries = usage.used_queries if usage else 0

    governor = QuotaGovernor()
    quota = await governor.get_quota_settings(workspace_id=workspace_id, session=session)

    limit = quota.monthly_token_limit
    budget = quota.monthly_budget_usd
    warning_pct = quota.warning_threshold_pct
    is_hard = quota.is_hard_enforced

    remaining_tokens = max(0, limit - used_tokens)
    remaining_budget_usd = budget * (remaining_tokens / max(1, limit))
    is_warning = bool(used_tokens >= (limit * warning_pct))
    is_exceeded = bool(is_hard and (used_tokens >= limit))

    return WorkspaceUsageDTO(
        workspace_id=workspace_id,
        billing_period_start=period_start.isoformat(),
        used_tokens=used_tokens,
        used_queries=used_queries,
        monthly_token_limit=limit,
        monthly_budget_usd=budget,
        warning_threshold_pct=warning_pct,
        is_hard_enforced=is_hard,
        remaining_tokens=remaining_tokens,
        remaining_budget_usd=remaining_budget_usd,
        is_warning=is_warning,
        is_exceeded=is_exceeded,
    )


@router.get("/workspace-user-quotas/{workspace_id}", response_model=list[WorkspaceUserQuotaDTO])
async def list_workspace_user_quotas(
    workspace_id: uuid.UUID,
    auth: Annotated[UserContext, Depends(require_role(Role.OWNER, Role.ADMIN, Role.PLATFORM_ADMIN))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Fetch all workspace members with their configured user quotas and consumed usage."""
    await require_workspace_admin_or_owner(workspace_id, auth, session)

    from backend.models.entities.user import User
    from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember
    from backend.modules.analytics.repositories.user_quota_repository import UserQuotaRepository

    u_repo = UserQuotaRepository(session)
    usage_repo = UsageRepository(session)
    period_start = usage_repo.get_current_period_start()

    governor = QuotaGovernor()
    ws_quota = await governor.get_quota_settings(workspace_id=workspace_id, session=session)
    ws_limit = ws_quota.monthly_token_limit

    # Fetch active members for workspace with their user details
    stmt = (
        select(WorkspaceMember, User)
        .join(User, WorkspaceMember.user_id == User.id)
        .where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.status == MemberStatus.ACTIVE.value,
        )
    )
    members_res = await session.execute(stmt)
    members_list = members_res.all()

    # Fetch configured user quotas
    configured_quotas = await u_repo.list_user_quotas(workspace_id)
    quota_by_user = {q.user_id: q for q in configured_quotas}

    results: list[WorkspaceUserQuotaDTO] = []
    for member, user in members_list:
        uq = quota_by_user.get(member.user_id)
        usage = await u_repo.get_user_usage(workspace_id, member.user_id, period_start)
        used_tokens = usage.used_tokens if usage else 0
        used_queries = usage.used_queries if usage else 0

        results.append(
            WorkspaceUserQuotaDTO(
                id=uq.id if uq else None,
                workspace_id=workspace_id,
                user_id=member.user_id,
                monthly_token_budget=uq.monthly_token_budget if uq else None,
                is_hard_enforced=uq.is_hard_enforced if uq else True,
                warning_threshold_pct=uq.warning_threshold_pct if uq else 0.80,
                user_email=user.email,
                user_display_name=user.display_name,
                member_role=member.role,
                used_tokens=used_tokens,
                used_queries=used_queries,
                workspace_token_limit=ws_limit,
            )
        )

    return results


@router.get("/workspace-user-quotas/{workspace_id}/me", response_model=WorkspaceUserQuotaDTO)
async def get_my_workspace_user_quota(
    workspace_id: uuid.UUID,
    auth: Annotated[UserContext, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Fetch current user's quota configuration and consumed usage within the workspace."""
    member = await get_workspace_member_or_raise(workspace_id, auth, session)

    from backend.models.entities.user import User
    from backend.modules.analytics.repositories.user_quota_repository import UserQuotaRepository

    u_repo = UserQuotaRepository(session)
    usage_repo = UsageRepository(session)
    period_start = usage_repo.get_current_period_start()

    governor = QuotaGovernor()
    ws_quota = await governor.get_quota_settings(workspace_id=workspace_id, session=session)

    uq = await u_repo.get_user_quota(workspace_id, auth.id)
    usage = await u_repo.get_user_usage(workspace_id, auth.id, period_start)

    stmt_user = select(User).where(User.id == auth.id)
    res_user = await session.execute(stmt_user)
    user_obj = res_user.scalar_one_or_none()

    return WorkspaceUserQuotaDTO(
        id=uq.id if uq else None,
        workspace_id=workspace_id,
        user_id=auth.id,
        monthly_token_budget=uq.monthly_token_budget if uq else None,
        is_hard_enforced=uq.is_hard_enforced if uq else True,
        warning_threshold_pct=uq.warning_threshold_pct if uq else 0.80,
        user_email=user_obj.email if user_obj else None,
        user_display_name=user_obj.display_name if user_obj else None,
        member_role=member.role if member else (auth.role or "MEMBER"),
        used_tokens=usage.used_tokens if usage else 0,
        used_queries=usage.used_queries if usage else 0,
        workspace_token_limit=ws_quota.monthly_token_limit,
    )


@router.put("/workspace-user-quotas/{workspace_id}/{user_id}", response_model=WorkspaceUserQuotaDTO)
async def update_workspace_user_quota(
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    req: WorkspaceUserQuotaUpdateDTO,
    auth: Annotated[UserContext, Depends(require_role(Role.OWNER, Role.ADMIN, Role.PLATFORM_ADMIN))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Update or set an individual member's token quota (OWNER, ADMIN, or PLATFORM_ADMIN)."""
    await require_workspace_admin_or_owner(workspace_id, auth, session)

    from backend.models.entities.user import User
    from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember
    from backend.modules.analytics.repositories.user_quota_repository import UserQuotaRepository

    # Verify target user is an active member
    stmt = select(WorkspaceMember, User).join(User, WorkspaceMember.user_id == User.id).where(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.user_id == user_id,
        WorkspaceMember.status == MemberStatus.ACTIVE.value,
    )
    res = await session.execute(stmt)
    target = res.first()
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found in this workspace.",
        )
    target_member, target_user = target

    # Budget of 0 or None means unconstrained (inherits workspace pool)
    budget = req.monthly_token_budget
    if budget == 0:
        budget = None

    governor = QuotaGovernor()
    ws_quota = await governor.get_quota_settings(workspace_id=workspace_id, session=session)
    if budget is not None and budget > ws_quota.monthly_token_limit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User token budget ({budget}) cannot exceed workspace token ceiling ({ws_quota.monthly_token_limit}).",
        )

    u_repo = UserQuotaRepository(session)
    saved = await u_repo.set_user_quota(
        workspace_id=workspace_id,
        user_id=user_id,
        monthly_token_budget=budget,
        is_hard_enforced=req.is_hard_enforced,
        warning_threshold_pct=req.warning_threshold_pct,
    )

    usage_repo = UsageRepository(session)
    period_start = usage_repo.get_current_period_start()
    usage = await u_repo.get_user_usage(workspace_id, user_id, period_start)

    return WorkspaceUserQuotaDTO(
        id=saved.id,
        workspace_id=workspace_id,
        user_id=user_id,
        monthly_token_budget=saved.monthly_token_budget,
        is_hard_enforced=saved.is_hard_enforced,
        warning_threshold_pct=saved.warning_threshold_pct,
        user_email=target_user.email,
        user_display_name=target_user.display_name,
        member_role=target_member.role,
        used_tokens=usage.used_tokens if usage else 0,
        used_queries=usage.used_queries if usage else 0,
        workspace_token_limit=ws_quota.monthly_token_limit,
    )

