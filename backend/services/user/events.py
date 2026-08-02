from dataclasses import dataclass

from backend.core.events.base import BaseEvent
from backend.core.events.types import EventType


@dataclass(frozen=True)
class UserProfileUpdatedEvent(BaseEvent):
    """Event emitted when a user's profile is updated."""
    event_type: EventType = EventType.USER_PROFILE_UPDATED
    user_id: str = ""
    changed_fields: list[str] = None
