"""FeatureFlagWorkspaceRule entity model for tenant-specific flag overrides."""

from datetime import datetime
from typing import Any
import uuid

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import BaseModel


class FeatureFlagWorkspaceRule(BaseModel):
    """Workspace-level override rule for a feature flag."""

    __tablename__ = "feature_flag_workspace_rules"
    __table_args__ = (
        UniqueConstraint("flag_id", "workspace_id", name="uq_flag_workspace"),
        CheckConstraint("rollout_percentage >= 0 AND rollout_percentage <= 100", name="chk_rollout_percentage"),
    )

    flag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("feature_flags.id", ondelete="CASCADE"),
        nullable=False,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    rollout_percentage: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    activation_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activation_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    targeting_conditions_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)
    custom_variant_json: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
