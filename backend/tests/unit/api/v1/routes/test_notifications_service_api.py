"""Unit and integration regression tests for in-app notifications and preferences."""

import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from backend.api.v1.schemas.notifications import NotificationDTO
from backend.core.auth.context import UserContext
from backend.core.permissions.rbac import Role
from backend.core.dependencies.auth import get_current_user
from backend.database.engine import get_async_session
from backend.models.entities.notification import NotificationCategory, NotificationSeverity
from backend.models.entities.user import User
from backend.services.notification.notification_service import NotificationService
from backend.main import app


@pytest.mark.asyncio
async def test_notification_service_crud_and_sanitization():
    """Test NotificationService persistence, unread counting, and open redirect protection."""
    async for db_session in get_async_session():
        # Load an existing user from the database to satisfy the foreign key constraint
        user_res = await db_session.execute(select(User).limit(1))
        existing_user = user_res.scalar_one_or_none()
        assert existing_user is not None, "Test database must have at least one user"

        user_id = existing_user.id
        tenant_id = existing_user.tenant_id or uuid.uuid4()

        service = NotificationService(db_session)

        # 1. Create notification with unsafe external action_url (must be sanitized to None)
        dto_unsafe = await service.create_and_publish(
            tenant_id=tenant_id,
            user_id=user_id,
            title="External Link Attempt",
            message="Checking open redirect protection",
            category=NotificationCategory.SECURITY.value,
            severity=NotificationSeverity.WARNING.value,
            action_url="https://attacker.com/malicious",
        )
        assert dto_unsafe.action_url is None

        # 2. Create notification with valid internal action_url
        dto_safe = await service.create_and_publish(
            tenant_id=tenant_id,
            user_id=user_id,
            title="Document Ready",
            message="Document processing completed successfully",
            category=NotificationCategory.DOCUMENT.value,
            severity=NotificationSeverity.INFO.value,
            action_url="/documents",
        )
        assert dto_safe.action_url == "/documents"

        # 3. Verify unread count is at least 2
        unread = await service.get_unread_count(tenant_id, user_id)
        assert unread.unread_count >= 2

        # 4. Mark safe notification as read
        read_dto = await service.mark_as_read(dto_safe.id, tenant_id, user_id)
        assert read_dto is not None
        assert read_dto.is_read is True
        assert read_dto.read_at is not None

        # 5. Mark all as read
        mark_all_res = await service.mark_all_as_read(tenant_id, user_id)
        assert mark_all_res.affected_count >= 1

        unread_final = await service.get_unread_count(tenant_id, user_id)
        assert unread_final.unread_count == 0

        # 6. Dismiss notification
        dismiss_res = await service.dismiss_notification(dto_safe.id, tenant_id, user_id)
        assert dismiss_res.success is True
        break


@pytest.mark.asyncio
async def test_notifications_rest_endpoints():
    """Test REST endpoints: list, unread-count, read mutation, and read-all."""
    async for db_session in get_async_session():
        user_res = await db_session.execute(select(User).limit(1))
        existing_user = user_res.scalar_one_or_none()
        assert existing_user is not None

        user_id = existing_user.id
        tenant_id = existing_user.tenant_id or uuid.uuid4()

        test_user = UserContext(
            id=user_id,
            email=existing_user.email,
            tenant_id=str(tenant_id),
            role=Role.MEMBER,
            is_active=True,
        )

        app.dependency_overrides[get_current_user] = lambda: test_user

        service = NotificationService(db_session)
        n1 = await service.create_and_publish(
            tenant_id=tenant_id,
            user_id=user_id,
            title="System Notice",
            message="Notice body",
            category=NotificationCategory.SYSTEM.value,
            severity=NotificationSeverity.INFO.value,
        )

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                # 1. GET /api/v1/notifications/unread-count
                resp = await client.get("/api/v1/notifications/unread-count")
                assert resp.status_code == 200
                assert resp.json()["unread_count"] >= 1

                # 2. GET /api/v1/notifications
                resp = await client.get("/api/v1/notifications?page=1&page_size=10")
                assert resp.status_code == 200
                data = resp.json()
                assert len(data["items"]) >= 1
                assert any(item["id"] == str(n1.id) for item in data["items"])

                # 3. PATCH /api/v1/notifications/{id}/read
                resp = await client.patch(f"/api/v1/notifications/{n1.id}/read")
                assert resp.status_code == 200
                assert resp.json()["is_read"] is True

                # 4. POST /api/v1/notifications/read-all
                resp = await client.post("/api/v1/notifications/read-all")
                assert resp.status_code == 200
                assert resp.json()["success"] is True

                # 5. DELETE /api/v1/notifications/{id}
                resp = await client.delete(f"/api/v1/notifications/{n1.id}")
                assert resp.status_code == 200
                assert resp.json()["success"] is True
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        break
