from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, BigInteger, Float, Boolean
from backend.database.base import Base

class TenantQuotaORM(Base):
    __tablename__ = "tenant_quotas"
    tenant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    monthly_token_limit: Mapped[int] = mapped_column(BigInteger)
    monthly_budget_usd: Mapped[float] = mapped_column(Float)
    warning_threshold_pct: Mapped[float] = mapped_column(Float, default=0.80)
    is_hard_enforced: Mapped[bool] = mapped_column(Boolean, default=True)
