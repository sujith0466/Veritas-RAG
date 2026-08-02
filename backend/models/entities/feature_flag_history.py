"""FeatureFlagHistory entity model for auditing and point-in-time rollbacks."""

from typing import Any
import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import BaseModel


class FeatureFlagHistory(BaseModel):
    """Immutable audit snapshot of feature flag and rule modifications."""

    __tablename__ = "feature_flag_history"

    flag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("feature_flags.id", ondelete="CASCADE"),
        nullable=False,
    )
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="SET NULL"),
        nullable=True,
    )
    changed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    change_action: Mapped[str] = mapped_column(String(50), nullable=False)
    change_reason: Mapped[str] = mapped_column(String(255), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    old_rule_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    new_rule_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
