"""Notification Delivery Log Entity."""

from datetime import datetime
from typing import Any
import uuid

from sqlalchemy import Integer, String, DateTime, Enum, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import BaseModel


class NotificationDeliveryLog(BaseModel):
    """Tracks outbound notification attempts (emails, webhooks) and their statuses."""

    __tablename__ = "notification_delivery_logs"

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        nullable=True,
        index=True,
    )
    type: Mapped[str] = mapped_column(
        Enum("EMAIL", "WEBHOOK", name="notification_type_enum"),
        nullable=False,
        index=True,
    )
    target: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )
    payload_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    status: Mapped[str] = mapped_column(
        Enum("PENDING", "SUCCESS", "FAILED_TRANSIENT", "FAILED_PERMANENT", name="delivery_status_enum"),
        nullable=False,
        default="PENDING",
        index=True,
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
    )
