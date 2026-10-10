"""Persistent in-app notification entity model."""

import datetime
from enum import StrEnum
from typing import Any
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import TenantAwareBaseModel


class NotificationCategory(StrEnum):
    SYSTEM = "SYSTEM"
    DOCUMENT = "DOCUMENT"
    SECURITY = "SECURITY"
    AI_RELIABILITY = "AI_RELIABILITY"


class NotificationSeverity(StrEnum):
    INFO = "INFO"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class Notification(TenantAwareBaseModel):
    """Persistent in-app notification for users and workspaces."""

    __tablename__ = "notifications"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=NotificationCategory.SYSTEM.value,
    )
    severity: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=NotificationSeverity.INFO.value,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    action_url: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )
    read_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        Index(
            "ix_notifications_tenant_user_read_created",
            "tenant_id",
            "user_id",
            "is_read",
            "created_at",
        ),
        Index(
            "ix_notifications_tenant_created",
            "tenant_id",
            "created_at",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Notification(id={self.id}, tenant_id={self.tenant_id}, "
            f"user_id={self.user_id}, category={self.category}, title='{self.title[:20]}')>"
        )
