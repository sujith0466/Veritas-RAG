"""Workspace event handlers."""

import structlog

from backend.core.events.dispatcher import get_dispatcher
from backend.core.events.types import EventType
from backend.core.security.jwt import get_jwt_service
from backend.services.workspace.events import (
    WorkspaceMemberRemovedEvent,
    WorkspaceMemberRoleUpdatedEvent,
)

logger = structlog.get_logger(__name__)


async def handle_member_role_updated(event: WorkspaceMemberRoleUpdatedEvent) -> None:
    """Handle role updates by invalidating active workspace tokens."""
    jwt_service = get_jwt_service()
    await jwt_service.revoke_user_workspace_tokens(event.user_id, event.workspace_id)
    logger.info(
        "Invalidated workspace tokens for role update",
        user_id=event.user_id,
        workspace_id=event.workspace_id,
    )


async def handle_member_removed(event: WorkspaceMemberRemovedEvent) -> None:
    """Handle member removal by invalidating active workspace tokens."""
    jwt_service = get_jwt_service()
    await jwt_service.revoke_user_workspace_tokens(event.user_id, event.workspace_id)
    logger.info(
        "Invalidated workspace tokens for member removal",
        user_id=event.user_id,
        workspace_id=event.workspace_id,
    )


def register_workspace_event_handlers() -> None:
    """Register all workspace domain event handlers."""
    dispatcher = get_dispatcher()
    dispatcher.subscribe(EventType.WORKSPACE_MEMBER_ROLE_UPDATED, handle_member_role_updated)
    dispatcher.subscribe(EventType.WORKSPACE_MEMBER_REMOVED, handle_member_removed)
    logger.debug("Registered workspace event handlers")
