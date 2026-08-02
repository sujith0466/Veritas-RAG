from fastapi import APIRouter

from backend.modules.analytics.schemas.analytics_dto import TenantQuotaDTO, TenantQuotaUpdateDTO

router = APIRouter(prefix="/analytics/v1/quotas", tags=["Quota"])


@router.get("/{tenant_id}", response_model=TenantQuotaDTO)
async def get_quota(tenant_id: str):
    return TenantQuotaDTO(
        tenant_id=tenant_id,
        monthly_token_limit=10000000,
        monthly_budget_usd=150.0,
        warning_threshold_pct=0.8,
        is_hard_enforced=True,
        remaining_tokens=9000000,
        remaining_budget_usd=140.0,
    )


@router.put("/{tenant_id}", response_model=TenantQuotaDTO)
async def update_quota(tenant_id: str, req: TenantQuotaUpdateDTO):
    return TenantQuotaDTO(
        tenant_id=tenant_id,
        monthly_token_limit=20000000,
        monthly_budget_usd=300.0,
        warning_threshold_pct=0.8,
        is_hard_enforced=True,
        remaining_tokens=19000000,
        remaining_budget_usd=290.0,
    )
