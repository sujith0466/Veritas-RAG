import uuid

from sqlalchemy import BigInteger, Boolean, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base


class TenantQuotaORM(Base):
    __tablename__ = "tenant_quotas"
    tenant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    monthly_token_limit: Mapped[int] = mapped_column(BigInteger)
    monthly_budget_usd: Mapped[float] = mapped_column(Float)
    warning_threshold_pct: Mapped[float] = mapped_column(Float, default=0.80)
    is_hard_enforced: Mapped[bool] = mapped_column(Boolean, default=True)
