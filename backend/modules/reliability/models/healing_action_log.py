from sqlalchemy.orm import Mapped, mapped_column
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
