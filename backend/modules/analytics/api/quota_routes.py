from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated

from backend.core.dependencies.database import get_db as get_db_session
from backend.core.auth.context import UserContext
from backend.core.dependencies.rbac import require_role
from backend.core.permissions.rbac import Role
from backend.modules.analytics.schemas.analytics_dto import TenantQuotaDTO, TenantQuotaUpdateDTO
from backend.modules.analytics.repositories.quota_repository import QuotaRepository
from backend.modules.analytics.services.quota import QuotaGovernor

router = APIRouter(prefix="/analytics/v1/quotas", tags=["Quota"])


@router.get("/{tenant_id}", response_model=TenantQuotaDTO)
async def get_quota(
    tenant_id: str,
    auth: Annotated[UserContext, Depends(require_role(Role.ADMIN, Role.OWNER, Role.PLATFORM_ADMIN))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Fetch the tenant's current quota settings and real-time remaining tokens from Redis."""
    # Ensure authorization isolation
    if auth.tenant_id != tenant_id and Role.from_str(auth.role) != Role.PLATFORM_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot access quota of another tenant.")
        
    repo = QuotaRepository(session)
    quota = await repo.get_by_tenant_id(tenant_id)
    
    if not quota:
        # Default initialization if missing
        quota = await repo.create_or_update(
            tenant_id=tenant_id,
            monthly_token_limit=10000000,
            monthly_budget_usd=150.0,
            warning_threshold_pct=0.8,
            is_hard_enforced=True,
        )
        
    governor = QuotaGovernor()
    remaining = await governor.get_remaining_tokens(tenant_id)
    
    # If uninitialized in redis, sync it from DB
    if remaining == 0:
        await governor.set_remaining_tokens(tenant_id, quota.monthly_token_limit)
        remaining = quota.monthly_token_limit

    return TenantQuotaDTO(
        tenant_id=tenant_id,
        monthly_token_limit=quota.monthly_token_limit,
        monthly_budget_usd=quota.monthly_budget_usd,
        warning_threshold_pct=quota.warning_threshold_pct,
        is_hard_enforced=quota.is_hard_enforced,
        remaining_tokens=remaining,
        remaining_budget_usd=quota.monthly_budget_usd * (remaining / max(1, quota.monthly_token_limit)),
    )


@router.put("/{tenant_id}", response_model=TenantQuotaDTO)
async def update_quota(
    tenant_id: str, 
    req: TenantQuotaUpdateDTO,
    auth: Annotated[UserContext, Depends(require_role(Role.OWNER, Role.PLATFORM_ADMIN))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
):
    """Update tenant quota limits and synchronize to Redis (OWNER or PLATFORM_ADMIN only)."""
    # Ensure authorization isolation
    if auth.tenant_id != tenant_id and Role.from_str(auth.role) != Role.PLATFORM_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot update quota of another tenant.")

    repo = QuotaRepository(session)
    # Fetch old quota to adjust remaining tokens difference safely
    old_quota = await repo.get_by_tenant_id(tenant_id)
    old_limit = old_quota.monthly_token_limit if old_quota else req.monthly_token_limit
    
    quota = await repo.create_or_update(
        tenant_id=tenant_id,
        monthly_token_limit=req.monthly_token_limit,
        monthly_budget_usd=req.monthly_budget_usd,
        warning_threshold_pct=req.warning_threshold_pct,
        is_hard_enforced=req.is_hard_enforced,
    )
    
    governor = QuotaGovernor()
    diff = req.monthly_token_limit - old_limit
    await governor.adjust_reservation_diff(tenant_id, diff)
    
    remaining = await governor.get_remaining_tokens(tenant_id)

    return TenantQuotaDTO(
        tenant_id=tenant_id,
        monthly_token_limit=quota.monthly_token_limit,
        monthly_budget_usd=quota.monthly_budget_usd,
        warning_threshold_pct=quota.warning_threshold_pct,
        is_hard_enforced=quota.is_hard_enforced,
        remaining_tokens=remaining,
        remaining_budget_usd=quota.monthly_budget_usd * (remaining / max(1, quota.monthly_token_limit)),
    )
