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



