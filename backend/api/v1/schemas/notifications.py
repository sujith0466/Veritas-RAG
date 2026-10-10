"""Pydantic schemas for in-app notifications API."""

from datetime import datetime
from typing import Any
import uuid

from pydantic import BaseModel, ConfigDict, Field


class NotificationDTO(BaseModel):
    """Data transfer object for in-app notification representation."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    user_id: uuid.UUID | None = None
    category: str
    severity: str
    title: str
    message: str
    action_url: str | None = None
    payload_json: dict[str, Any] | None = None
    is_read: bool
    read_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationListResponse(BaseModel):
    """Paginated list of notifications with unread counter."""

    items: list[NotificationDTO]
    total: int
    page: int
    page_size: int
    unread_count: int


class UnreadCountResponse(BaseModel):
    """Summary unread counter for navbar bell hydration."""

    unread_count: int


class NotificationActionResponse(BaseModel):
    """Generic acknowledgment for mutation actions."""

    success: bool = True
    affected_count: int = 1
    message: str = "Operation completed successfully"
