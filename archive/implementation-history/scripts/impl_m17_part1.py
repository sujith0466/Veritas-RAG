import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

def main():
    print("Starting Milestone 17.1 Implementation...")
    
    dirs = [
        "backend/modules/alerts/schemas",
        "backend/modules/alerts/channels",
        "backend/modules/alerts/models",
        "backend/modules/alerts/repositories",
        "backend/modules/alerts/services",
        "backend/modules/alerts/api",
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
        with open(f"{d}/__init__.py", "w") as f:
            pass
    with open("backend/modules/alerts/__init__.py", "w") as f:
        pass

    # 1. schemas/errors.py
    with open("backend/modules/alerts/schemas/errors.py", "w") as f:
        f.write("""from enum import StrEnum
from backend.core.exceptions.base import RAGuardException

class AlertErrorCode(StrEnum):
    CHANNEL_DELIVERY_FAILED = "ALT_001"
    RULE_EVALUATION_ERROR = "ALT_002"

class AlertDomainException(RAGuardException):
    def __init__(self, message: str, error_code: str, detail: dict | None = None):
        super().__init__(message=message, error_code=error_code, detail=detail)
""")

    # 2. schemas/alert_dto.py
    with open("backend/modules/alerts/schemas/alert_dto.py", "w") as f:
        f.write("""from pydantic import BaseModel
from typing import Any

class ChannelConfigDTO(BaseModel):
    channel_type: str
    target_url: str | None = None
    routing_key: str | None = None

class AlertRuleCreateDTO(BaseModel):
    name: str
    metric_name: str
    operator: str
    threshold_value: str
    channels_config: list[ChannelConfigDTO]
    cooldown_minutes: int = 15
    is_active: bool = True

class AlertRuleDTO(AlertRuleCreateDTO):
    id: str
    tenant_id: str

class AlertRuleUpdateDTO(BaseModel):
    is_active: bool

class AlertPayloadDTO(BaseModel):
    tenant_id: str
    rule_name: str
    event_type: str
    metric_name: str
    value: str
    threshold: str

class AlertHistoryDTO(BaseModel):
    id: str
    rule_id: str
    tenant_id: str
    channel_type: str
    status: str
    triggered_at: str
""")

    # 3. channels/base.py
    with open("backend/modules/alerts/channels/base.py", "w") as f:
        f.write("""from abc import ABC, abstractmethod
from backend.modules.alerts.schemas.alert_dto import AlertPayloadDTO, ChannelConfigDTO

class BaseNotificationChannel(ABC):
    @abstractmethod
    async def send_alert(self, payload: AlertPayloadDTO, config: ChannelConfigDTO) -> bool:
        pass
""")

    # 4. models/alert_rule.py
    with open("backend/modules/alerts/models/alert_rule.py", "w") as f:
        f.write("""from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import String, Integer, Boolean
import uuid
from backend.database.base import Base

class AlertRuleORM(Base):
    __tablename__ = "alert_rules"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(128))
    metric_name: Mapped[str] = mapped_column(String(64))
    operator: Mapped[str] = mapped_column(String(32))
    threshold_value: Mapped[str] = mapped_column(String(128))
    channels_config: Mapped[list[dict]] = mapped_column(JSONB)
    cooldown_minutes: Mapped[int] = mapped_column(Integer, default=15)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
""")

    # 5. models/alert_history.py
    with open("backend/modules/alerts/models/alert_history.py", "w") as f:
        f.write("""from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import String, ForeignKey, Text, DateTime, func
import uuid
from datetime import datetime
from backend.database.base import Base

class AlertHistoryORM(Base):
    __tablename__ = "alert_history"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    rule_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("alert_rules.id"))
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    channel_type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32))
    payload_sent: Mapped[dict] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
""")

    # 6. repositories/alert_repository.py
    with open("backend/modules/alerts/repositories/alert_repository.py", "w") as f:
        f.write("""from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.modules.alerts.models.alert_rule import AlertRuleORM
from backend.modules.alerts.models.alert_history import AlertHistoryORM

class AlertRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_active_rules(self, tenant_id: str, metric_name: str) -> list[AlertRuleORM]:
        query = select(AlertRuleORM).where(
            AlertRuleORM.tenant_id == tenant_id,
            AlertRuleORM.metric_name == metric_name,
            AlertRuleORM.is_active == True
        )
        result = await self._session.execute(query)
        return list(result.scalars().all())
        
    async def save_history(self, history: AlertHistoryORM) -> AlertHistoryORM:
        self._session.add(history)
        await self._session.commit()
        return history
""")

    # 7. alembic migration
    migration_path = "alembic/versions/0017_alerting_engine_schema.py"
    with open(migration_path, "w") as f:
        f.write("""\"\"\"alerting engine schema

Revision ID: 0017
Revises: 0016
Create Date: 2026-07-20 10:00:00.000000

\"\"\"
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0017'
down_revision = '0016'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table('alert_rules',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('metric_name', sa.String(length=64), nullable=False),
        sa.Column('operator', sa.String(length=32), nullable=False),
        sa.Column('threshold_value', sa.String(length=128), nullable=False),
        sa.Column('channels_config', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('cooldown_minutes', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_alert_rules_tenant_id'), 'alert_rules', ['tenant_id'], unique=False)

    op.create_table('alert_history',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('rule_id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('channel_type', sa.String(length=32), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('payload_sent', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('triggered_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['rule_id'], ['alert_rules.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_alert_history_tenant_id'), 'alert_history', ['tenant_id'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_alert_history_tenant_id'), table_name='alert_history')
    op.drop_table('alert_history')
    op.drop_index(op.f('ix_alert_rules_tenant_id'), table_name='alert_rules')
    op.drop_table('alert_rules')
""")

    print("Milestone 17.1 completed.")

if __name__ == "__main__":
    main()
