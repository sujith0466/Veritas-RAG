"""Unit and Security Verification Tests for Section 9 / WP-9.

Verifies:
1. D-20 In-App Governance Notifications:
   - Promotion: emits in-app notification with workspace_id to promoted user.
   - Demotion: emits in-app notification with workspace_id to demoted user.
   - Suspension: emits user-scoped in-app notification (tenant_id=None, workspace_id=None, user_id=target).
   - Reactivation: emits in-app notification with workspace_id to reactivated user.
   - Removal: emits user-scoped in-app notification (tenant_id=None, workspace_id=None, user_id=target).
   - Non-blocking isolation: notification failure never aborts membership transactions.
   - Personal notification retrieval: removed/suspended user (tenant_id=None) can retrieve personal notifications.
2. D-21 Option 2 Audit Log Separation & Platform Diagnostic Endpoint:
   - GET /api/v1/audit-logs is strictly restricted to customer OWNER/ADMIN for their own tenant_id.
   - GET /api/v1/audit-logs rejects platform roles (PLATFORM_ADMIN, PLATFORM_AUDITOR, PLATFORM_SUPPORT) with HTTP 403.
   - GET /api/v1/audit-logs rejects regular members (MEMBER) with HTTP 403.
   - GET /api/v1/platform/audit-logs/inspect requires PLATFORM_ADMIN or PLATFORM_AUDITOR.
   - Dedicated endpoint strictly requires mandatory header X-Justification-Ticket-ID.
   - Dedicated endpoint logs immutable diagnostic access record via record_diagnostic_access.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from backend.api.v1.routes.audit_logs import router as audit_logs_router
from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import get_db
from backend.services.workspace.events import (
    WorkspaceMemberRemovedEvent,
    WorkspaceMemberRestoredEvent,
    WorkspaceMemberRoleUpdatedEvent,
    WorkspaceMemberSuspendedEvent,
)
from backend.core.exceptions import get_exception_handlers
from backend.core.permissions.rbac import Role
from backend.models.entities.notification import (
    Notification,
    NotificationCategory,
    NotificationSeverity,
)
from backend.repositories.interfaces.audit_log_repository import IAuditLogRepository
from backend.core.dependencies.database import get_audit_log_repository
from backend.services.workspace.handlers import (
    _persist_notification_safe,
    handle_member_removed,
    handle_member_restored,
    handle_member_role_updated,
    handle_member_suspended,
)


# ==============================================================================
# 1. D-20: Governance In-App Notification Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_persist_notification_safe_error_isolation():
    """Verify that notification persistence failure logs warning and does not raise."""
    with patch("backend.services.workspace.handlers.get_session_factory", side_effect=RuntimeError("DB down")):
        # Must not raise
        await _persist_notification_safe(
            tenant_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            title="Test",
            message="Test message",
        )


@pytest.mark.asyncio
async def test_handle_member_role_updated_promotion_notification():
    """Verify role promotion emits workspace-scoped notification to target user."""
    ws_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    target_user_id = uuid.uuid4()

    event = WorkspaceMemberRoleUpdatedEvent(
        workspace_id=str(ws_id),
        actor_id=str(actor_id),
        user_id=str(target_user_id),
        old_role="MEMBER",
        new_role="ADMIN",
    )

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_ctx = MagicMock()
    mock_ctx.__aenter__.return_value = mock_session
    mock_ctx.__aexit__.return_value = None

    with (
        patch("backend.services.workspace.handlers.get_session_factory", return_value=MagicMock(return_value=mock_ctx)),
        patch("backend.services.workspace.handlers.get_jwt_service") as mock_jwt,
    ):
        mock_jwt.return_value.revoke_user_workspace_tokens = AsyncMock()
        await handle_member_role_updated(event)

        assert mock_session.add.call_count == 1
        notif = mock_session.add.call_args[0][0]
        assert isinstance(notif, Notification)
        assert notif.user_id == target_user_id
        assert notif.tenant_id == ws_id
        assert notif.payload_json["workspace_id"] == str(ws_id)
        assert "promoted" in notif.title.lower()
        mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_member_role_updated_demotion_notification():
    """Verify role demotion emits workspace-scoped notification to target user."""
    ws_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    target_user_id = uuid.uuid4()

    event = WorkspaceMemberRoleUpdatedEvent(
        workspace_id=str(ws_id),
        actor_id=str(actor_id),
        user_id=str(target_user_id),
        old_role="ADMIN",
        new_role="MEMBER",
    )

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_ctx = MagicMock()
    mock_ctx.__aenter__.return_value = mock_session
    mock_ctx.__aexit__.return_value = None

    with (
        patch("backend.services.workspace.handlers.get_session_factory", return_value=MagicMock(return_value=mock_ctx)),
        patch("backend.services.workspace.handlers.get_jwt_service") as mock_jwt,
    ):
        mock_jwt.return_value.revoke_user_workspace_tokens = AsyncMock()
        await handle_member_role_updated(event)

        assert mock_session.add.call_count == 1
        notif = mock_session.add.call_args[0][0]
        assert isinstance(notif, Notification)
        assert notif.user_id == target_user_id
        assert notif.tenant_id == ws_id
        assert notif.payload_json["workspace_id"] == str(ws_id)
        assert "updated" in notif.title.lower()
        mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_member_suspended_user_scoped_notification():
    """D-20 Option A: Verify suspended member receives user-scoped notification with workspace_id=None."""
    ws_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    target_user_id = uuid.uuid4()

    event = WorkspaceMemberSuspendedEvent(
        workspace_id=str(ws_id),
        actor_id=str(actor_id),
        user_id=str(target_user_id),
    )

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_ctx = MagicMock()
    mock_ctx.__aenter__.return_value = mock_session
    mock_ctx.__aexit__.return_value = None

    with (
        patch("backend.services.workspace.handlers.get_session_factory", return_value=MagicMock(return_value=mock_ctx)),
        patch("backend.services.workspace.handlers.get_jwt_service") as mock_jwt,
    ):
        mock_jwt.return_value.revoke_user_workspace_tokens = AsyncMock()
        await handle_member_suspended(event)

        assert mock_session.add.call_count == 1
        notif = mock_session.add.call_args[0][0]
        assert isinstance(notif, Notification)
        assert notif.user_id == target_user_id
        assert notif.tenant_id is None
        assert notif.payload_json["workspace_id"] is None
        assert notif.payload_json["scope"] == "user_scoped"
        assert "suspended" in notif.title.lower()
        mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_member_restored_notification():
    """Verify reactivated member receives in-app notification with workspace_id."""
    ws_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    target_user_id = uuid.uuid4()

    event = WorkspaceMemberRestoredEvent(
        workspace_id=str(ws_id),
        actor_id=str(actor_id),
        user_id=str(target_user_id),
    )

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_ctx = MagicMock()
    mock_ctx.__aenter__.return_value = mock_session
    mock_ctx.__aexit__.return_value = None

    with patch("backend.services.workspace.handlers.get_session_factory", return_value=MagicMock(return_value=mock_ctx)):
        await handle_member_restored(event)

        assert mock_session.add.call_count == 1
        notif = mock_session.add.call_args[0][0]
        assert isinstance(notif, Notification)
        assert notif.user_id == target_user_id
        assert notif.tenant_id == ws_id
        assert "reactivated" in notif.title.lower()
        mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_member_removed_user_scoped_notification():
    """D-20 Option A: Verify removed member receives user-scoped notification with workspace_id=None."""
    ws_id = uuid.uuid4()
    actor_id = uuid.uuid4()
    target_user_id = uuid.uuid4()

    event = WorkspaceMemberRemovedEvent(
        workspace_id=str(ws_id),
        actor_id=str(actor_id),
        user_id=str(target_user_id),
    )

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_ctx = MagicMock()
    mock_ctx.__aenter__.return_value = mock_session
    mock_ctx.__aexit__.return_value = None

    with (
        patch("backend.services.workspace.handlers.get_session_factory", return_value=MagicMock(return_value=mock_ctx)),
        patch("backend.services.workspace.handlers.get_jwt_service") as mock_jwt,
    ):
        mock_jwt.return_value.revoke_user_workspace_tokens = AsyncMock()
        await handle_member_removed(event)

        assert mock_session.add.call_count == 1
        notif = mock_session.add.call_args[0][0]
        assert isinstance(notif, Notification)
        assert notif.user_id == target_user_id
        assert notif.tenant_id is None
        assert notif.payload_json["workspace_id"] is None
        assert notif.payload_json["scope"] == "user_scoped"
        assert "removed" in notif.title.lower()
        mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_personal_notification_retrieval_after_removal_or_suspension():
    """Verify personal notification endpoint allows removed/suspended users (no tenant_id) to retrieve notifications."""
    from backend.api.v1.routes.notifications import router as notifications_router
    from backend.services.notification.notification_service import NotificationService
    from backend.api.v1.schemas.notifications import NotificationListResponse, NotificationDTO
    from datetime import datetime, UTC

    test_notif_app = FastAPI()
    for exc_class, handler in get_exception_handlers():
        test_notif_app.add_exception_handler(exc_class, handler)
    test_notif_app.include_router(notifications_router, prefix="/api/v1")

    target_user_id = uuid.uuid4()
    # User token has tenant_id=None (removed/suspended user with personal session)
    user_context = UserContext(
        id=target_user_id,
        email="removed_member@example.com",
        role=Role.MEMBER,
        is_active=True,
        is_verified=True,
        tenant_id=None,
    )

    mock_notif_dto = NotificationDTO(
        id=uuid.uuid4(),
        tenant_id=None,
        user_id=target_user_id,
        category="SYSTEM",
        severity="INFO",
        title="Removed from Workspace",
        message="You have been removed from this workspace.",
        action_url=None,
        payload_json={"scope": "user_scoped", "event": "member_removed", "workspace_id": None},
        is_read=False,
        read_at=None,
        created_at=datetime.now(UTC),
    )

    mock_resp = NotificationListResponse(
        items=[mock_notif_dto],
        total=1,
        page=1,
        page_size=20,
        unread_count=1,
    )

    test_notif_app.dependency_overrides[get_current_user] = lambda: user_context
    test_notif_app.dependency_overrides[get_db] = lambda: AsyncMock()

    with patch.object(NotificationService, "list_notifications", new_callable=AsyncMock) as mock_list:
        mock_list.return_value = mock_resp
        try:
            client = TestClient(test_notif_app)
            res = client.get("/api/v1/notifications")
            assert res.status_code == 200
            data = res.json()
            assert data["total"] == 1
            assert data["items"][0]["user_id"] == str(target_user_id)
            assert data["items"][0]["tenant_id"] is None
            assert data["items"][0]["title"] == "Removed from Workspace"

            # Verify service was invoked with tenant_id=None and user_id=target_user_id
            mock_list.assert_awaited_once()
            call_kwargs = mock_list.call_args[1]
            assert call_kwargs["tenant_id"] is None
            assert call_kwargs["user_id"] == target_user_id
        finally:
            test_notif_app.dependency_overrides.clear()


# ==============================================================================
# 2. D-21 Option 2: Route Security and Platform Diagnostic Access Tests
# ==============================================================================

app = FastAPI()
for exc_class, handler in get_exception_handlers():
    app.add_exception_handler(exc_class, handler)
app.include_router(audit_logs_router, prefix="/api/v1")


def make_user_context(role: Role, tenant_id: uuid.UUID | None = None) -> UserContext:
    return UserContext(
        id=uuid.uuid4(),
        email=f"{role.value.lower()}@example.com",
        role=role,
        is_active=True,
        is_verified=True,
        tenant_id=str(tenant_id) if tenant_id else None,
    )


def test_customer_audit_logs_owner_admin_allowed():
    """Customer OWNER and ADMIN can read their own workspace audit logs."""
    ws_id = uuid.uuid4()
    mock_repo = AsyncMock(spec=IAuditLogRepository)
    mock_repo.search_logs.return_value = ([], 0)

    for role in (Role.OWNER, Role.ADMIN):
        user = make_user_context(role, ws_id)
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_audit_log_repository] = lambda: mock_repo
        app.dependency_overrides[get_db] = lambda: AsyncMock()

        try:
            client = TestClient(app)
            res = client.get("/api/v1/audit-logs")
            assert res.status_code == 200, f"Role {role} failed customer audit log access"
        finally:
            app.dependency_overrides.clear()


def test_customer_audit_logs_prohibits_platform_roles():
    """Platform roles are rejected on customer audit route with HTTP 403 Forbidden."""
    ws_id = uuid.uuid4()
    mock_repo = AsyncMock(spec=IAuditLogRepository)

    for role in (Role.PLATFORM_ADMIN, Role.PLATFORM_AUDITOR, Role.PLATFORM_SUPPORT):
        user = make_user_context(role, ws_id)
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_audit_log_repository] = lambda: mock_repo
        app.dependency_overrides[get_db] = lambda: AsyncMock()

        try:
            client = TestClient(app)
            res = client.get("/api/v1/audit-logs")
            assert res.status_code == 403, f"Platform role {role} was not rejected with 403"
            err_msg = res.json().get("error", {}).get("message", res.json().get("detail", ""))
            assert "prohibited from" in err_msg.lower()
        finally:
            app.dependency_overrides.clear()


def test_customer_audit_logs_rejects_regular_member():
    """Regular member and viewer cannot access workspace audit logs."""
    ws_id = uuid.uuid4()
    mock_repo = AsyncMock(spec=IAuditLogRepository)

    for role in (Role.MEMBER, Role.VIEWER):
        user = make_user_context(role, ws_id)
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_audit_log_repository] = lambda: mock_repo
        app.dependency_overrides[get_db] = lambda: AsyncMock()

        try:
            client = TestClient(app)
            res = client.get("/api/v1/audit-logs")
            assert res.status_code == 403
            err_msg = res.json().get("error", {}).get("message", res.json().get("detail", ""))
            assert "insufficient permissions" in err_msg.lower()
        finally:
            app.dependency_overrides.clear()


def test_platform_diagnostic_inspect_requires_ticket():
    """Diagnostic route rejects requests without justification ticket."""
    ws_id = uuid.uuid4()
    mock_repo = AsyncMock(spec=IAuditLogRepository)

    user = make_user_context(Role.PLATFORM_ADMIN)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_audit_log_repository] = lambda: mock_repo
    app.dependency_overrides[get_db] = lambda: AsyncMock()

    try:
        client = TestClient(app)
        res = client.get(f"/api/v1/platform/audit-logs/inspect?workspace_id={ws_id}")
        assert res.status_code == 400
        err_msg = res.json().get("error", {}).get("message", res.json().get("detail", ""))
        assert "diagnostic ticket header" in err_msg.lower()
    finally:
        app.dependency_overrides.clear()


def test_platform_diagnostic_inspect_prohibits_non_platform_roles():
    """Non-platform roles cannot access diagnostic audit endpoint."""
    ws_id = uuid.uuid4()
    mock_repo = AsyncMock(spec=IAuditLogRepository)

    for role in (Role.OWNER, Role.ADMIN, Role.MEMBER):
        user = make_user_context(role, ws_id)
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_audit_log_repository] = lambda: mock_repo
        app.dependency_overrides[get_db] = lambda: AsyncMock()

        try:
            client = TestClient(app)
            res = client.get(
                f"/api/v1/platform/audit-logs/inspect?workspace_id={ws_id}",
                headers={"X-Justification-Ticket-ID": "TICKET-12345"},
            )
            assert res.status_code == 403
            err_msg = res.json().get("error", {}).get("message", res.json().get("detail", ""))
            assert "only platform diagnostic roles" in err_msg.lower()
        finally:
            app.dependency_overrides.clear()


def test_platform_diagnostic_inspect_success_and_audit():
    """Valid platform diagnostic request succeeds and logs immutable audit trail."""
    ws_id = uuid.uuid4()
    mock_repo = AsyncMock(spec=IAuditLogRepository)
    mock_repo.search_logs.return_value = ([], 0)

    user = make_user_context(Role.PLATFORM_ADMIN)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_audit_log_repository] = lambda: mock_repo
    app.dependency_overrides[get_db] = lambda: AsyncMock()

    with patch("backend.api.v1.routes.audit_logs.record_diagnostic_access", new_callable=AsyncMock) as mock_record:
        try:
            client = TestClient(app)
            res = client.get(
                f"/api/v1/platform/audit-logs/inspect?workspace_id={ws_id}",
                headers={"X-Justification-Ticket-ID": "SEC-TICKET-9999"},
            )
            assert res.status_code == 200
            mock_record.assert_awaited_once()
            call_kwargs = mock_record.call_args[1]
            assert call_kwargs["ticket_id"] == "SEC-TICKET-9999"
            assert call_kwargs["tenant_id"] == ws_id
            assert call_kwargs["action"] == "DIAGNOSTIC_AUDIT_LOG_READ"
        finally:
            app.dependency_overrides.clear()
