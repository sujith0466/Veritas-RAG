"""Workspace User Quota Entity Model.

Defines user-level monthly token quotas within a workspace, with hierarchical enforcement.
"""

from datetime import datetime
import uuid

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base


class WorkspaceUserQuotaORM(Base):
    """Authoritative user-level monthly token quota configuration.

    Semantic Rules:
    - monthly_token_budget is NULL: User has NO individual cap, meaning their usage is bounded
      solely by the workspace's remaining monthly token limit.
    - monthly_token_budget is an Integer: The user's consumption cannot exceed this specific cap
      in the current billing period, in addition to the overall workspace budget.
    """

    __tablename__ = "workspace_user_quotas"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    monthly_token_budget: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )
    warning_threshold_pct: Mapped[float] = mapped_column(
        Float,
        default=0.80,
        nullable=False,
    )
    is_hard_enforced: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_workspace_user_quotas_workspace_user"),
    )
