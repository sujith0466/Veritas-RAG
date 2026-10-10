"""Repository for in-app notifications."""

from datetime import UTC, datetime
from typing import Sequence
import uuid

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.entities.notification import Notification
from backend.repositories.base import BaseRepository


class NotificationRepository(BaseRepository[Notification]):
    """Async repository for querying and mutating in-app notifications."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Notification)

    async def create_notification(
        self,
        tenant_id: uuid.UUID,
        title: str,
        message: str,
        user_id: uuid.UUID | None = None,
        category: str = "SYSTEM",
        severity: str = "INFO",
        action_url: str | None = None,
        payload_json: dict | None = None,
    ) -> Notification:
        """Create and persist a new in-app notification."""
        notification = Notification(
            tenant_id=tenant_id,
            user_id=user_id,
            category=category,
            severity=severity,
            title=title,
            message=message,
            action_url=action_url,
            payload_json=payload_json,
            is_read=False,
            read_at=None,
        )
        self.session.add(notification)
        await self.session.flush()
        await self.session.refresh(notification)
        return notification

    async def list_notifications(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        category: str | None = None,
        unread_only: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[Sequence[Notification], int]:
        """Fetch paginated notifications with tenant and user isolation."""
        base_filters = [
            Notification.tenant_id == tenant_id,
            Notification.is_deleted.is_(False),
            or_(Notification.user_id == user_id, Notification.user_id.is_(None)),
        ]

        if category:
            base_filters.append(Notification.category == category.upper())
        if unread_only:
            base_filters.append(Notification.is_read.is_(False))

        # Total count query
        count_stmt = select(func.count(Notification.id)).where(*base_filters)
        total_count = (await self.session.execute(count_stmt)).scalar() or 0

        # Items query
        offset = max(0, (page - 1) * page_size)
        items_stmt = (
            select(Notification)
            .where(*base_filters)
            .order_by(Notification.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.session.execute(items_stmt)
        items = result.scalars().all()

        return items, total_count

    async def get_unread_count(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> int:
        """Return the total count of unread active notifications."""
        stmt = select(func.count(Notification.id)).where(
            Notification.tenant_id == tenant_id,
            Notification.is_deleted.is_(False),
            Notification.is_read.is_(False),
            or_(Notification.user_id == user_id, Notification.user_id.is_(None)),
        )
        count = (await self.session.execute(stmt)).scalar()
        return count or 0

    async def mark_as_read(
        self,
        notification_id: uuid.UUID,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Notification | None:
        """Mark a single authorized notification as read."""
        stmt = select(Notification).where(
            Notification.id == notification_id,
            Notification.tenant_id == tenant_id,
            Notification.is_deleted.is_(False),
            or_(Notification.user_id == user_id, Notification.user_id.is_(None)),
        )
        result = await self.session.execute(stmt)
        notification = result.scalar_one_or_none()

        if notification and not notification.is_read:
            notification.is_read = True
            notification.read_at = datetime.now(UTC)
            await self.session.flush()

        return notification

    async def mark_all_as_read(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> int:
        """Mark all unread active notifications for this user as read."""
        stmt = (
            update(Notification)
            .where(
                Notification.tenant_id == tenant_id,
                Notification.is_deleted.is_(False),
                Notification.is_read.is_(False),
                or_(Notification.user_id == user_id, Notification.user_id.is_(None)),
            )
            .values(
                is_read=True,
                read_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount

    async def dismiss_notification(
        self,
        notification_id: uuid.UUID,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """Soft-delete an authorized notification."""
        stmt = select(Notification).where(
            Notification.id == notification_id,
            Notification.tenant_id == tenant_id,
            Notification.is_deleted.is_(False),
            or_(Notification.user_id == user_id, Notification.user_id.is_(None)),
        )
        result = await self.session.execute(stmt)
        notification = result.scalar_one_or_none()

        if notification:
            notification.is_deleted = True
            notification.updated_at = datetime.now(UTC)
            await self.session.flush()
            return True
        return False
