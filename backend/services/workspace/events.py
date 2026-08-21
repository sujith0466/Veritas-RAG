from dataclasses import dataclass
from typing import Any

from backend.core.events.base import BaseEvent
from backend.core.events.types import EventType


@dataclass(frozen=True)
class WorkspaceArchivedEvent(BaseEvent):
    """Event emitted when a workspace is successfully archived."""
    event_type: EventType = EventType.WORKSPACE_ARCHIVED
    workspace_id: str = ""
    actor_id: str = ""
    details: dict[str, Any] | None = None


@dataclass(frozen=True)
class WorkspaceRestoredEvent(BaseEvent):
    """Event emitted when a workspace is successfully restored."""
    event_type: EventType = EventType.WORKSPACE_RESTORED
    workspace_id: str = ""
    actor_id: str = ""
    details: dict[str, Any] | None = None


@dataclass(frozen=True)
class WorkspaceSuspendedEvent(BaseEvent):
    """Event emitted when a workspace is successfully suspended by Platform Admin."""
    event_type: EventType = EventType.WORKSPACE_SUSPENDED
    workspace_id: str = ""
    actor_id: str = ""
    reason_code: str = ""
    reason_text: str | None = None
    details: dict[str, Any] | None = None


@dataclass(frozen=True)
class WorkspaceUnsuspendedEvent(BaseEvent):
    """Event emitted when a workspace is successfully unsuspended by Platform Admin."""
    event_type: EventType = EventType.WORKSPACE_UNSUSPENDED
    workspace_id: str = ""
    actor_id: str = ""
    reason_text: str | None = None
    details: dict[str, Any] | None = None


@dataclass(frozen=True)
class WorkspaceSoftDeletedEvent(BaseEvent):
    """Event emitted when a workspace is soft deleted."""
    event_type: EventType = EventType.WORKSPACE_SOFT_DELETED
    workspace_id: str = ""
    actor_id: str = ""
    reason_code: str | None = None
    reason_text: str | None = None
    details: dict[str, Any] | None = None


@dataclass(frozen=True)
class WorkspacePurgingStartedEvent(BaseEvent):
    """Event emitted when workspace purging begins."""
    event_type: EventType = EventType.WORKSPACE_PURGING_STARTED
    workspace_id: str = ""
    details: dict[str, Any] | None = None


@dataclass(frozen=True)
class WorkspaceHardDeletedEvent(BaseEvent):
    """Event emitted when a workspace is permanently hard deleted."""
    event_type: EventType = EventType.WORKSPACE_HARD_DELETED
    workspace_id: str = ""
    actor_id: str = ""
    details: dict[str, Any] | None = None


@dataclass(frozen=True)
class WorkspaceSettingsUpdatedEvent(BaseEvent):
    """Event emitted when workspace settings are updated."""
    event_type: EventType = EventType.WORKSPACE_SETTINGS_UPDATED
    workspace_id: str = ""
    schema_version: int = 1
    version: int = 1
    settings_hash: str = ""
    changed_by_user_id: str | None = None
    details: dict[str, Any] | None = None


@dataclass(frozen=True)
class WorkspaceSettingsResetEvent(BaseEvent):
    """Event emitted when workspace settings are reset to defaults."""
    event_type: EventType = EventType.WORKSPACE_SETTINGS_RESET
    workspace_id: str = ""
    category: str | None = None
    actor_id: str = ""
    details: dict[str, Any] | None = None


@dataclass(frozen=True)
class WorkspaceSettingsImportedEvent(BaseEvent):
    """Event emitted when workspace settings are imported."""
    event_type: EventType = EventType.WORKSPACE_SETTINGS_IMPORTED
    workspace_id: str = ""
    actor_id: str = ""
    version: int = 1
    settings_hash: str = ""
    details: dict[str, Any] | None = None


@dataclass(frozen=True)
class WorkspaceBrandingUpdatedEvent(BaseEvent):
    """Event emitted when workspace branding configuration is published or updated."""
    event_type: EventType = EventType.WORKSPACE_BRANDING_UPDATED
    workspace_id: str = ""
    actor_id: str = ""
    version: int = 1
    settings_hash: str = ""
    is_rollback: bool = False
    details: dict[str, Any] | None = None


# ── Epic 4: Workspace Invitations ──────────────────────────────────────────────

@dataclass(frozen=True)
class WorkspaceInvitationCreatedEvent(BaseEvent):
    """Event emitted when a workspace invitation is created and sent."""
    event_type: EventType = EventType.WORKSPACE_INVITATION_CREATED
    workspace_id: str = ""
    invitation_id: str = ""
    invited_by_user_id: str = ""
    email: str = ""
    role: str = ""
    expires_at: str = ""
    details: dict[str, Any] | None = None


@dataclass(frozen=True)
class WorkspaceInvitationResentEvent(BaseEvent):
    """Event emitted when a workspace invitation is resent with rotated token."""
    event_type: EventType = EventType.WORKSPACE_INVITATION_RESENT
    workspace_id: str = ""
    invitation_id: str = ""
    actor_id: str = ""
    email: str = ""
    resend_count: int = 0
    expires_at: str = ""
    details: dict[str, Any] | None = None


@dataclass(frozen=True)
class WorkspaceInvitationRevokedEvent(BaseEvent):
    """Event emitted when a workspace invitation is revoked."""
    event_type: EventType = EventType.WORKSPACE_INVITATION_REVOKED
    workspace_id: str = ""
    invitation_id: str = ""
    actor_id: str = ""
    email: str = ""
    details: dict[str, Any] | None = None


@dataclass(frozen=True)
class WorkspaceInvitationExpiredEvent(BaseEvent):
    """Event emitted when a workspace invitation expires."""
    event_type: EventType = EventType.WORKSPACE_INVITATION_EXPIRED
    workspace_id: str = ""
    invitation_id: str = ""
    email: str = ""
    details: dict[str, Any] | None = None


@dataclass(frozen=True)
class WorkspaceInvitationAcceptedEvent(BaseEvent):
    """Event emitted when a workspace invitation is successfully accepted."""
    event_type: EventType = EventType.WORKSPACE_INVITATION_ACCEPTED
    workspace_id: str = ""
    invitation_id: str = ""
    member_id: str = ""
    user_id: str = ""
    email: str = ""
    role: str = ""
    details: dict[str, Any] | None = None


@dataclass(frozen=True)
class WorkspaceInvitationAcceptFailedEvent(BaseEvent):
    """Event emitted when an invitation acceptance fails due to security or state errors."""
    event_type: EventType = EventType.WORKSPACE_INVITATION_ACCEPT_FAILED
    workspace_id: str = ""
    token_hash: str = ""
    user_id: str = ""
    reason: str = ""
    details: dict[str, Any] | None = None


@dataclass(frozen=True)
class WorkspaceMemberRoleUpdatedEvent(BaseEvent):
    """Event emitted when a workspace member's role is updated."""
    event_type: EventType = EventType.WORKSPACE_MEMBER_ROLE_UPDATED
    workspace_id: str = ""
    member_id: str = ""
    user_id: str = ""
    actor_id: str = ""
    old_role: str = ""
    new_role: str = ""
    details: dict[str, Any] | None = None


@dataclass(frozen=True)
class WorkspaceMemberSuspendedEvent(BaseEvent):
    """Event emitted when a workspace member is suspended."""
    event_type: EventType = EventType.WORKSPACE_MEMBER_SUSPENDED
    workspace_id: str = ""
    member_id: str = ""
    user_id: str = ""
    actor_id: str = ""
    details: dict[str, Any] | None = None


@dataclass(frozen=True)
class WorkspaceMemberRestoredEvent(BaseEvent):
    """Event emitted when a workspace member is restored from suspension."""
    event_type: EventType = EventType.WORKSPACE_MEMBER_RESTORED
    workspace_id: str = ""
    member_id: str = ""
    user_id: str = ""
    actor_id: str = ""
    details: dict[str, Any] | None = None


@dataclass(frozen=True)
class WorkspaceMemberRemovedEvent(BaseEvent):
    """Event emitted when a workspace member is soft removed."""
    event_type: EventType = EventType.WORKSPACE_MEMBER_REMOVED
    workspace_id: str = ""
    member_id: str = ""
    user_id: str = ""
    actor_id: str = ""
    details: dict[str, Any] | None = None



