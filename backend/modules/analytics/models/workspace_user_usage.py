"""Workspace User Usage Entity Model.

Tracks durable aggregate token and query usage per user per workspace per billing period.
"""

import datetime
import uuid

from sqlalchemy import BigInteger, CheckConstraint, Date, DateTime, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base


class WorkspaceUserUsage(Base):
    """Tracks durable aggregate token and query usage per user per workspace per billing period."""

    __tablename__ = "workspace_user_usages"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    billing_period_start: Mapped[datetime.date] = mapped_column(
        Date,
        primary_key=True,
    )
    used_tokens: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )
    used_queries: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint("used_tokens >= 0", name="chk_workspace_user_usages_tokens_positive"),
        CheckConstraint("used_queries >= 0", name="chk_workspace_user_usages_queries_positive"),
    )
