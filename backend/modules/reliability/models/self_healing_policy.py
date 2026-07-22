import uuid

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base


class SelfHealingPolicyORM(Base):
    __tablename__ = "self_healing_policies"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    auto_parameter_tuning: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_model_rotation: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_quarantine_sweep: Mapped[bool] = mapped_column(Boolean, default=True)
    max_interventions_per_hour: Mapped[int] = mapped_column(Integer, default=10)
