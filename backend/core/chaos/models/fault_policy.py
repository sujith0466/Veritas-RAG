from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, Float, Boolean, DateTime, func
import uuid
from datetime import datetime
from backend.database.base import Base

class FaultPolicyORM(Base):
    __tablename__ = "fault_policies"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    chaos_token: Mapped[str] = mapped_column(String(128), index=True)
    fault_type: Mapped[str] = mapped_column(String(64))
    target_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    error_rate_pct: Mapped[float] = mapped_column(Float, default=1.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now)
