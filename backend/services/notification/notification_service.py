"""Notification service managing in-app persistence, authorization, and dispatch."""

import json
from typing import Any
from urllib.parse import urlparse
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.api.v1.schemas.notifications import (
    NotificationActionResponse,
    NotificationDTO,
    NotificationListResponse,
    UnreadCountResponse,
)
from backend.cache.client import get_redis_client
from backend.models.entities.notification import (
    Notification,
    NotificationCategory,
    NotificationSeverity,
)
from backend.repositories.notification_repository import NotificationRepository

logger = structlog.get_logger(__name__)


class NotificationService:
    """Business logic service for managing and dispatching in-app notifications."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = NotificationRepository(session)

    @staticmethod
    def _sanitize_action_url(url: str | None) -> str | None:
        """Validate that action_url is a safe relative internal route."""
        if not url:
            return None
        stripped = url.strip()
        parsed = urlparse(stripped)
        # Block external schemes and protocols to prevent open redirects
        if parsed.scheme or parsed.netloc or not stripped.startswith("/"):
            logger.warning("Rejected unsafe external or malformed notification action_url", url=stripped)
            return None
        return stripped

    async def create_and_publish(
        self,
        tenant_id: uuid.UUID,
        title: str,
        message: str,
        user_id: uuid.UUID | None = None,
        category: str = NotificationCategory.SYSTEM.value,
        severity: str = NotificationSeverity.INFO.value,
        action_url: str | None = None,
        payload_json: dict[str, Any] | None = None,
    ) -> NotificationDTO:
        """Persist a notification to the database and broadcast it via Redis Pub/Sub."""
        safe_action_url = self._sanitize_action_url(action_url)

        notification = await self.repo.create_notification(
            tenant_id=tenant_id,
            user_id=user_id,
            category=category,
            severity=severity,
            title=title.strip()[:255],
            message=message.strip(),
            action_url=safe_action_url,
            payload_json=payload_json,
        )
        await self.session.commit()
        await self.session.refresh(notification)

        dto = NotificationDTO.model_validate(notification)

        # Real-time WebSocket push via Redis Pub/Sub
        try:
            redis = get_redis_client()
            if redis:
                channel = f"workspace:{tenant_id}:notifications"
                payload = {
                    "type": f"NOTIFICATION_{category}",
                    "id": str(dto.id),
                    "tenant_id": str(dto.tenant_id),
                    "user_id": str(dto.user_id) if dto.user_id else None,
                    "category": dto.category,
                    "severity": dto.severity,
                    "title": dto.title,
                    "message": dto.message,
                    "action_url": dto.action_url,
                    "payload": dto.payload_json or {},
                    "is_read": dto.is_read,
                    "timestamp": dto.created_at.isoformat(),
                }
                await redis.publish(channel, json.dumps(payload))
        except Exception as e:
            logger.warning("Failed to publish real-time notification to Redis", error=str(e))

        return dto

    async def list_notifications(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        category: str | None = None,
        unread_only: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> NotificationListResponse:
        """Retrieve paginated notifications and accurate unread count."""
        items, total = await self.repo.list_notifications(
            tenant_id=tenant_id,
            user_id=user_id,
            category=category,
            unread_only=unread_only,
            page=page,
            page_size=page_size,
        )
        unread_count = await self.repo.get_unread_count(tenant_id, user_id)

        return NotificationListResponse(
            items=[NotificationDTO.model_validate(item) for item in items],
            total=total,
            page=page,
            page_size=page_size,
            unread_count=unread_count,
        )

    async def get_unread_count(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> UnreadCountResponse:
        """Retrieve authoritative count of unread notifications."""
        count = await self.repo.get_unread_count(tenant_id, user_id)
        return UnreadCountResponse(unread_count=count)

    async def mark_as_read(
        self,
        notification_id: uuid.UUID,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> NotificationDTO | None:
        """Mark a single authorized notification as read."""
        notification = await self.repo.mark_as_read(
            notification_id=notification_id,
            tenant_id=tenant_id,
            user_id=user_id,
        )
        if notification:
            await self.session.commit()
            await self.session.refresh(notification)
            return NotificationDTO.model_validate(notification)
        return None

    async def mark_all_as_read(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> NotificationActionResponse:
        """Mark all unread active notifications for this user as read."""
        count = await self.repo.mark_all_as_read(tenant_id, user_id)
        await self.session.commit()
        return NotificationActionResponse(
            success=True,
            affected_count=count,
            message=f"Marked {count} notifications as read",
        )

    async def dismiss_notification(
        self,
        notification_id: uuid.UUID,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> NotificationActionResponse:
        """Dismiss (soft delete) a notification."""
        success = await self.repo.dismiss_notification(
            notification_id=notification_id,
            tenant_id=tenant_id,
            user_id=user_id,
        )
        if success:
            await self.session.commit()
            return NotificationActionResponse(
                success=True,
                affected_count=1,
                message="Notification dismissed successfully",
            )
        return NotificationActionResponse(
            success=False,
            affected_count=0,
            message="Notification not found or access denied",
        )
