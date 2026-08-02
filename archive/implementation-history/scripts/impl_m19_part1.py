import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

def main():
    print("Starting Milestone 19.1 Implementation...")
    
    dirs = [
        "backend/modules/analytics/models",
        "backend/modules/analytics/services",
        "backend/modules/analytics/api",
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
        init_file = f"{d}/__init__.py"
        if not os.path.exists(init_file):
            with open(init_file, "w") as f:
                pass

    # 1. Update schemas/errors.py
    errors_path = "backend/modules/analytics/schemas/errors.py"
    with open(errors_path, "a") as f:
        f.write("""
class QuotaExceededError(RAGuardException):
    def __init__(self, message: str):
        super().__init__(message=message, error_code="ANA_QTA_001")

class InvalidPricingModelError(RAGuardException):
    def __init__(self, message: str):
        super().__init__(message=message, error_code="ANA_PRC_001")
""")

    # 2. Update schemas/analytics_dto.py
    dto_path = "backend/modules/analytics/schemas/analytics_dto.py"
    with open(dto_path, "a") as f:
        f.write("""
# --- Phase 19 ROI & Quota DTOs ---
class ROIAttributionDTO(BaseModel):
    tenant_id: str
    window_days: int
    queries_trusted: int
    hallucinations_blocked: int
    ticket_savings_usd: float
    incident_savings_usd: float
    total_llm_cost_usd: float
    net_roi_usd: float

class TokenUsageDTO(BaseModel):
    id: str
    tenant_id: str
    correlation_id: str
    provider: str
    model_name: str
    prompt_tokens: int
    completion_tokens: int
    total_cost_usd: float

class TenantQuotaDTO(BaseModel):
    tenant_id: str
    monthly_token_limit: int
    monthly_budget_usd: float
    warning_threshold_pct: float
    is_hard_enforced: bool
    remaining_tokens: int
    remaining_budget_usd: float

class TenantQuotaUpdateDTO(BaseModel):
    monthly_token_limit: int | None = None
    monthly_budget_usd: float | None = None
    warning_threshold_pct: float | None = None
    is_hard_enforced: bool | None = None

class TrendForecastDTO(BaseModel):
    tenant_id: str
    projected_cost_90d_usd: float
    projected_tokens_90d: int
""")

    # 3. models/token_usage.py
    with open("backend/modules/analytics/models/token_usage.py", "w") as f:
        f.write("""from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, Float, DateTime, func
import uuid
from datetime import datetime
from backend.database.base import Base

class TokenUsageORM(Base):
    __tablename__ = "token_usages"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    correlation_id: Mapped[str] = mapped_column(String(128), index=True)
    provider: Mapped[str] = mapped_column(String(64))
    model_name: Mapped[str] = mapped_column(String(128))
    prompt_tokens: Mapped[int] = mapped_column(Integer)
    completion_tokens: Mapped[int] = mapped_column(Integer)
    total_cost_usd: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
""")

    # 4. models/tenant_quota.py
    with open("backend/modules/analytics/models/tenant_quota.py", "w") as f:
        f.write("""from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, BigInteger, Float, Boolean
from backend.database.base import Base

class TenantQuotaORM(Base):
    __tablename__ = "tenant_quotas"
    tenant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    monthly_token_limit: Mapped[int] = mapped_column(BigInteger)
    monthly_budget_usd: Mapped[float] = mapped_column(Float)
    warning_threshold_pct: Mapped[float] = mapped_column(Float, default=0.80)
    is_hard_enforced: Mapped[bool] = mapped_column(Boolean, default=True)
""")

    # 5. services/pricing.py
    with open("backend/modules/analytics/services/pricing.py", "w") as f:
        f.write("""from backend.modules.analytics.schemas.errors import InvalidPricingModelError

class PricingEngine:
    def __init__(self):
        # Micro-dollars per token (e.g. $0.005 per 1K -> 0.000005 per token)
        self.pricing_table = {
            "gpt-4o": {"prompt": 0.000005, "completion": 0.000015},
            "text-embedding-3-large": {"prompt": 0.00000013, "completion": 0.0},
            "anthropic-claude-3-opus": {"prompt": 0.000015, "completion": 0.000075}
        }

    def compute_cost(self, provider: str, model_name: str, prompt_tokens: int, completion_tokens: int) -> float:
        rates = self.pricing_table.get(model_name)
        if not rates:
            raise InvalidPricingModelError(f"Model {model_name} not found in pricing table")
        return (prompt_tokens * rates["prompt"]) + (completion_tokens * rates["completion"])
""")

    # 6. alembic migration
    migration_path = "alembic/versions/0019_enterprise_roi_analytics.py"
    with open(migration_path, "w") as f:
        f.write("""\"\"\"enterprise roi analytics schema

Revision ID: 0019
Revises: 0018
Create Date: 2026-07-20 12:00:00.000000

\"\"\"
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0019'
down_revision = '0018'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table('tenant_quotas',
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('monthly_token_limit', sa.BigInteger(), nullable=False),
        sa.Column('monthly_budget_usd', sa.Float(), nullable=False),
        sa.Column('warning_threshold_pct', sa.Float(), nullable=False),
        sa.Column('is_hard_enforced', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('tenant_id')
    )

    op.create_table('token_usages',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('correlation_id', sa.String(length=128), nullable=False),
        sa.Column('provider', sa.String(length=64), nullable=False),
        sa.Column('model_name', sa.String(length=128), nullable=False),
        sa.Column('prompt_tokens', sa.Integer(), nullable=False),
        sa.Column('completion_tokens', sa.Integer(), nullable=False),
        sa.Column('total_cost_usd', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_token_usages_correlation_id'), 'token_usages', ['correlation_id'], unique=False)
    op.create_index(op.f('ix_token_usages_tenant_id'), 'token_usages', ['tenant_id'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_token_usages_tenant_id'), table_name='token_usages')
    op.drop_index(op.f('ix_token_usages_correlation_id'), table_name='token_usages')
    op.drop_table('token_usages')
    op.drop_table('tenant_quotas')
""")

    print("Milestone 19.1 completed.")

if __name__ == "__main__":
    main()
