import datetime
from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.auth.context import UserContext
from backend.core.dependencies.database import get_db as get_db_session
from backend.core.dependencies.rbac import require_role
from backend.core.dependencies.workspace import get_workspace_member_or_raise
from backend.core.permissions.rbac import Role
from backend.modules.analytics.models.tenant_quota import TenantQuotaORM
from backend.modules.analytics.repositories.quota_repository import QuotaRepository
from backend.modules.analytics.repositories.usage_repository import UsageRepository
from backend.modules.analytics.schemas.analytics_dto import (
    TenantQuotaDTO,
    TenantQuotaUpdateDTO,
    WorkspaceUsageDTO,
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

    if ws_uuid:
        await get_workspace_member_or_raise(ws_uuid, auth, session)
    elif auth.tenant_id != tenant_id and Role.from_str(auth.role) != Role.PLATFORM_ADMIN:
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
    auth: Annotated[UserContext, Depends(require_role(Role.OWNER, Role.PLATFORM_ADMIN))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Update quota limits (OWNER or PLATFORM_ADMIN only)."""
    ws_uuid = None
    try:
        ws_uuid = uuid.UUID(tenant_id)
    except (ValueError, TypeError):
        pass

    if ws_uuid:
        await get_workspace_member_or_raise(ws_uuid, auth, session)
    elif auth.tenant_id != tenant_id and Role.from_str(auth.role) != Role.PLATFORM_ADMIN:
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
