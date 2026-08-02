"""Domain events for Feature Flags."""

from dataclasses import dataclass
from typing import Any

from backend.core.events.base import BaseEvent
from backend.core.events.types import EventType


@dataclass(frozen=True)
class FeatureFlagCreatedEvent(BaseEvent):
    """Event emitted when a new feature flag is created."""
    event_type: EventType = EventType.FEATURE_FLAG_CREATED
    flag_key: str = ""
    actor_id: str = ""
    category: str = ""
    details: dict[str, Any] | None = None


@dataclass(frozen=True)
class FeatureFlagUpdatedEvent(BaseEvent):
    """Event emitted when a master feature flag definition is updated."""
    event_type: EventType = EventType.FEATURE_FLAG_UPDATED
    flag_key: str = ""
    actor_id: str = ""
    version: int = 1
    details: dict[str, Any] | None = None


@dataclass(frozen=True)
class FeatureFlagKillswitchTriggeredEvent(BaseEvent):
    """Event emitted when a feature flag emergency kill switch is activated/deactivated."""
    event_type: EventType = EventType.FEATURE_FLAG_KILLSWITCH_TRIGGERED
    flag_key: str = ""
    actor_id: str = ""
    is_active: bool = True
    reason: str = ""
    details: dict[str, Any] | None = None


@dataclass(frozen=True)
class FeatureFlagRuleUpdatedEvent(BaseEvent):
    """Event emitted when a workspace override rule is modified."""
    event_type: EventType = EventType.FEATURE_FLAG_RULE_UPDATED
    flag_key: str = ""
    workspace_id: str = ""
    actor_id: str = ""
    version: int = 1
    is_enabled: bool = True
    rollout_percentage: int = 100
    details: dict[str, Any] | None = None
