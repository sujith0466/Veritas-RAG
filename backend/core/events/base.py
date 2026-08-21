"""Base event class for the Veritas RAG internal event system.

Events are immutable value objects that describe something that has happened
in the domain. They carry no behaviour — they only carry data.

Usage:
    class DocumentUploaded(BaseEvent):
        event_type = EventType.DOCUMENT_UPLOADED
        document_id: str
        tenant_id: str
        filename: str

    event = DocumentUploaded(document_id="abc", tenant_id="t1", filename="policy.pdf")
    await dispatcher.publish(event)
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
import uuid

from .types import EventType


@dataclass(frozen=True)
class BaseEvent:
    """Immutable base class for all Veritas RAG domain events.

    Attributes:
        event_id: Unique identifier for this event instance.
        event_type: The type of event (from EventType enum).
        occurred_at: UTC timestamp when the event occurred.
        correlation_id: Optional correlation ID from the originating HTTP request.
    """

    event_type: EventType
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str | None = field(default=None)

    def to_dict(self) -> dict[str, Any]:
        """Serialise event to a plain dict for logging or queuing."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "occurred_at": self.occurred_at.isoformat(),
            "correlation_id": self.correlation_id,
        }
