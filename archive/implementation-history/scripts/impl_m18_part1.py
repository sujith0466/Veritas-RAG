import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

def main():
    print("Starting Milestone 18.1 Implementation...")

    dirs = [
        "backend/modules/reliability/workers",
        "backend/modules/reliability/models",
        "backend/modules/reliability/repositories",
        "backend/modules/reliability/api",
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
        init_file = f"{d}/__init__.py"
        if not os.path.exists(init_file):
            with open(init_file, "w") as f:
                pass

    # 1. Update schemas/errors.py
    errors_path = "backend/modules/reliability/schemas/errors.py"
    with open(errors_path, "a") as f:
        f.write("""
class SelfHealingPolicyError(RAGuardException):
    def __init__(self, message: str):
        super().__init__(message=message, error_code="REL_GOV_001")

class RotationFailedError(RAGuardException):
    def __init__(self, message: str):
        super().__init__(message=message, error_code="REL_GOV_002")
""")

    # 2. Update schemas/reliability_dto.py
    dto_path = "backend/modules/reliability/schemas/reliability_dto.py"
    with open(dto_path, "a") as f:
        f.write("""
# --- Phase 18 Governor DTOs ---
class HealingActionDTO(BaseModel):
    id: str
    tenant_id: str
    action_type: str
    trigger_reason: str
    changes_applied: dict
    is_rolled_back: bool
    executed_at: str

class SelfHealingPolicyDTO(BaseModel):
    id: str
    tenant_id: str
    auto_parameter_tuning: bool = True
    auto_model_rotation: bool = True
    auto_quarantine_sweep: bool = True
    max_interventions_per_hour: int = 10

class SelfHealingPolicyUpdateDTO(BaseModel):
    auto_parameter_tuning: bool | None = None
    auto_model_rotation: bool | None = None
    auto_quarantine_sweep: bool | None = None
    max_interventions_per_hour: int | None = None

class ParameterOverrideDTO(BaseModel):
    retrieval_top_k: int | None = None
    similarity_threshold: float | None = None
    max_retry_budget: int | None = None
    reflection_strictness: float | None = None
""")

    # 3. models/self_healing_policy.py
    with open("backend/modules/reliability/models/self_healing_policy.py", "w") as f:
        f.write("""from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, Boolean
import uuid
from backend.database.base import Base

class SelfHealingPolicyORM(Base):
    __tablename__ = "self_healing_policies"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    auto_parameter_tuning: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_model_rotation: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_quarantine_sweep: Mapped[bool] = mapped_column(Boolean, default=True)
    max_interventions_per_hour: Mapped[int] = mapped_column(Integer, default=10)
""")

    # 4. models/healing_action_log.py
    with open("backend/modules/reliability/models/healing_action_log.py", "w") as f:
        f.write("""from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import String, Text, Boolean, DateTime, func
import uuid
from datetime import datetime
from backend.database.base import Base

class HealingActionLogORM(Base):
    __tablename__ = "healing_actions_log"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    action_type: Mapped[str] = mapped_column(String(64))
    trigger_reason: Mapped[str] = mapped_column(Text)
    changes_applied: Mapped[dict] = mapped_column(JSONB)
    is_rolled_back: Mapped[bool] = mapped_column(Boolean, default=False)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
""")

    # 5. repositories/governor_repository.py
    with open("backend/modules/reliability/repositories/governor_repository.py", "w") as f:
        f.write("""from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.modules.reliability.models.self_healing_policy import SelfHealingPolicyORM
from backend.modules.reliability.models.healing_action_log import HealingActionLogORM

class GovernorRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_policy(self, tenant_id: str) -> SelfHealingPolicyORM | None:
        query = select(SelfHealingPolicyORM).where(SelfHealingPolicyORM.tenant_id == tenant_id)
        res = await self._session.execute(query)
        return res.scalar_one_or_none()

    async def save_action_log(self, log: HealingActionLogORM) -> HealingActionLogORM:
        self._session.add(log)
        await self._session.commit()
        return log
""")

    # 6. alembic migration
    migration_path = "alembic/versions/0018_self_healing_governor.py"
    with open(migration_path, "w") as f:
        f.write("""\"\"\"self healing governor schema

Revision ID: 0018
Revises: 0017
Create Date: 2026-07-20 11:00:00.000000

\"\"\"
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0018'
down_revision = '0017'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table('self_healing_policies',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('auto_parameter_tuning', sa.Boolean(), nullable=False),
        sa.Column('auto_model_rotation', sa.Boolean(), nullable=False),
        sa.Column('auto_quarantine_sweep', sa.Boolean(), nullable=False),
        sa.Column('max_interventions_per_hour', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_self_healing_policies_tenant_id'), 'self_healing_policies', ['tenant_id'], unique=False)

    op.create_table('healing_actions_log',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('action_type', sa.String(length=64), nullable=False),
        sa.Column('trigger_reason', sa.Text(), nullable=False),
        sa.Column('changes_applied', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('is_rolled_back', sa.Boolean(), nullable=False),
        sa.Column('executed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_healing_actions_log_tenant_id'), 'healing_actions_log', ['tenant_id'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_healing_actions_log_tenant_id'), table_name='healing_actions_log')
    op.drop_table('healing_actions_log')
    op.drop_index(op.f('ix_self_healing_policies_tenant_id'), table_name='self_healing_policies')
    op.drop_table('self_healing_policies')
""")

    print("Milestone 18.1 completed.")

if __name__ == "__main__":
    main()
