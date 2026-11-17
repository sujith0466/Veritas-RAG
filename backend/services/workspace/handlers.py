"""Workspace event handlers."""

import uuid
import structlog

from backend.core.events.dispatcher import get_dispatcher
from backend.core.events.types import EventType
from backend.core.security.jwt import get_jwt_service
from backend.database.engine import get_session_factory
from backend.models.entities.notification import (
    Notification,
    NotificationCategory,
    NotificationSeverity,
)
from backend.services.workspace.events import (
    WorkspaceMemberRemovedEvent,
    WorkspaceMemberRestoredEvent,
    WorkspaceMemberRoleUpdatedEvent,
    WorkspaceMemberSuspendedEvent,
)

logger = structlog.get_logger(__name__)


def _to_uuid(val: str | uuid.UUID | None) -> uuid.UUID | None:
    if not val:
        return None
    if isinstance(val, uuid.UUID):
        return val
    try:
        return uuid.UUID(str(val))
    except (ValueError, TypeError):
        return None


async def _persist_notification_safe(
    tenant_id: str | uuid.UUID,
    user_id: str | uuid.UUID,
    title: str,
    message: str,
    payload_json: dict | None = None,
    action_url: str | None = None,
) -> None:
    """Non-blocking, failure-isolated, idempotent notification persistence (D-20)."""
    t_id = _to_uuid(tenant_id)
    u_id = _to_uuid(user_id)
    if not u_id:
        return

    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            notif = Notification(
                tenant_id=t_id,
                user_id=u_id,
                category=NotificationCategory.SYSTEM.value,
                severity=NotificationSeverity.INFO.value,
                title=title[:255],
                message=message,
                payload_json=payload_json,
                action_url=action_url,
            )
            session.add(notif)
            await session.commit()
            logger.info("Persisted governance notification", user_id=str(u_id), title=title)
    except Exception as e:
        logger.warning(
            "Non-blocking governance notification delivery failed",
            user_id=str(u_id),
            workspace_id=str(t_id),
            error=str(e),
        )


async def handle_member_role_updated(event: WorkspaceMemberRoleUpdatedEvent) -> None:
    """Handle role updates by invalidating active workspace tokens and emitting in-app notification."""
    jwt_service = get_jwt_service()
    await jwt_service.revoke_user_workspace_tokens(event.user_id, event.workspace_id)
    logger.info(
        "Invalidated workspace tokens for role update",
        user_id=event.user_id,
        workspace_id=event.workspace_id,
    )

    new_role = (event.new_role or "").strip().upper()
    if new_role == "ADMIN":
        title = "Role Promoted to Admin"
        message = "You have been promoted to Admin in this workspace."
    else:
        title = f"Role Updated to {new_role.title()}"
        message = f"Your role in this workspace has been updated to {new_role}."

    await _persist_notification_safe(
        tenant_id=event.workspace_id,
        user_id=event.user_id,
        title=title,
        message=message,
        payload_json={
            "scope": "workspace_scoped",
            "event": "member_role_updated",
            "old_role": event.old_role,
            "new_role": event.new_role,
            "workspace_id": event.workspace_id,
        },
        action_url=f"/workspaces/{event.workspace_id}/members",
    )


async def handle_member_suspended(event: WorkspaceMemberSuspendedEvent) -> None:
    """Handle member suspension by invalidating active tokens and emitting user-scoped notification (D-20 Option A)."""
    jwt_service = get_jwt_service()
    await jwt_service.revoke_user_workspace_tokens(event.user_id, event.workspace_id)
    logger.info(
        "Invalidated workspace tokens for member suspension",
        user_id=event.user_id,
        workspace_id=event.workspace_id,
    )

    await _persist_notification_safe(
        tenant_id=None,
        user_id=event.user_id,
        title="Workspace Membership Suspended",
        message="Your membership in this workspace has been suspended by an administrator.",
        payload_json={
            "scope": "user_scoped",
            "event": "member_suspended",
            "workspace_id": None,
            "target_workspace_id": event.workspace_id,
        },
    )


async def handle_member_restored(event: WorkspaceMemberRestoredEvent) -> None:
    """Handle member reactivation by emitting in-app notification (D-20)."""
    await _persist_notification_safe(
        tenant_id=event.workspace_id,
        user_id=event.user_id,
        title="Workspace Membership Reactivated",
        message="Your membership in this workspace has been restored to active status.",
        payload_json={
            "scope": "user_scoped",
            "event": "member_reactivated",
            "workspace_id": event.workspace_id,
        },
        action_url=f"/workspaces/{event.workspace_id}",
    )


async def handle_member_removed(event: WorkspaceMemberRemovedEvent) -> None:
    """Handle member removal by invalidating tokens and emitting user-scoped notification (D-20 Option A)."""
    jwt_service = get_jwt_service()
    await jwt_service.revoke_user_workspace_tokens(event.user_id, event.workspace_id)
    logger.info(
        "Invalidated workspace tokens for member removal",
        user_id=event.user_id,
        workspace_id=event.workspace_id,
    )

    await _persist_notification_safe(
        tenant_id=None,
        user_id=event.user_id,
        title="Removed from Workspace",
        message="You have been removed from this workspace.",
        payload_json={
            "scope": "user_scoped",
            "event": "member_removed",
            "workspace_id": None,
            "target_workspace_id": event.workspace_id,
        },
    )


def register_workspace_event_handlers() -> None:
    """Register all workspace domain event handlers."""
    dispatcher = get_dispatcher()
    dispatcher.subscribe(EventType.WORKSPACE_MEMBER_ROLE_UPDATED, handle_member_role_updated)
    dispatcher.subscribe(EventType.WORKSPACE_MEMBER_SUSPENDED, handle_member_suspended)
    dispatcher.subscribe(EventType.WORKSPACE_MEMBER_RESTORED, handle_member_restored)
    dispatcher.subscribe(EventType.WORKSPACE_MEMBER_REMOVED, handle_member_removed)
    logger.debug("Registered workspace event handlers")
