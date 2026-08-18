from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.modules.analytics.models.tenant_quota import TenantQuotaORM
from backend.database.base import Base

class QuotaRepository:
    """Repository for managing TenantQuotaORM settings."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_tenant_id(self, tenant_id: str) -> TenantQuotaORM | None:
        """Fetch the quota settings for a tenant."""
        stmt = select(TenantQuotaORM).where(TenantQuotaORM.tenant_id == tenant_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_or_update(
        self,
        tenant_id: str,
        monthly_token_limit: int,
        monthly_budget_usd: float,
        warning_threshold_pct: float,
        is_hard_enforced: bool,
    ) -> TenantQuotaORM:
        """Create or update a tenant's quota settings."""
        quota = await self.get_by_tenant_id(tenant_id)
        if not quota:
            quota = TenantQuotaORM(
                tenant_id=tenant_id,
                monthly_token_limit=monthly_token_limit,
                monthly_budget_usd=monthly_budget_usd,
                warning_threshold_pct=warning_threshold_pct,
                is_hard_enforced=is_hard_enforced,
            )
            self.session.add(quota)
        else:
            quota.monthly_token_limit = monthly_token_limit
            quota.monthly_budget_usd = monthly_budget_usd
            quota.warning_threshold_pct = warning_threshold_pct
            quota.is_hard_enforced = is_hard_enforced

        await self.session.commit()
        await self.session.refresh(quota)
        return quota
