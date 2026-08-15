"""Async in-process event dispatcher for RAGuard AI.

Provides a lightweight publish/subscribe mechanism for internal domain events.
This is NOT a message queue replacement — it is a synchronous in-process bus
for decoupling modules within the same process.

For cross-process events (e.g., triggering a Celery task from a domain event),
the handler itself is responsible for enqueuing the Celery task.

Usage:
    # Registration (done once at startup via the application factory)
    dispatcher = EventDispatcher()
    dispatcher.subscribe(EventType.DOCUMENT_UPLOADED, my_async_handler)

    # Publishing (from business logic)
    await dispatcher.publish(DocumentUploaded(document_id="abc", ...))
"""

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable

import structlog

from .base import BaseEvent
from .types import EventType

logger = structlog.get_logger(__name__)

# Type alias for event handler functions
EventHandler = Callable[[BaseEvent], Awaitable[None]]


class EventDispatcher:
    """In-process async event bus.

    Thread safety: not guaranteed. Designed for use within a single async
    FastAPI worker process.
    """

    def __init__(self) -> None:
        self._handlers: dict[EventType, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Register an async handler for a specific event type.

        Args:
            event_type: The EventType to listen for.
            handler: An async callable that receives the event instance.
        """
        self._handlers[event_type].append(handler)
        logger.debug(
            "Event handler registered",
            event_type=event_type,
            handler=handler.__qualname__,
        )

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Remove a previously registered handler."""
        handlers = self._handlers.get(event_type, [])
        try:
            handlers.remove(handler)
        except ValueError:
            pass

    async def publish(self, event: BaseEvent) -> None:
        """Publish an event to all registered handlers.

        Handlers are invoked concurrently via asyncio.gather.
        If a handler raises an exception, it is logged but does NOT
        propagate — other handlers continue to execute.

        Args:
            event: The domain event to publish.
        """
        handlers = self._handlers.get(event.event_type, [])
        
        # Globally dispatch to webhook worker if tenant_id is present
        from backend.tasks.webhooks import deliver_webhook_event_task
        event_dict = event.to_dict()
        tenant_id = getattr(event, 'tenant_id', event_dict.get('tenant_id'))
        if tenant_id:
            try:
                deliver_webhook_event_task.delay(
                    tenant_id_str=str(tenant_id),
                    event_type=event.event_type.value,
                    payload=event_dict
                )
            except Exception as e:
                logger.error("Failed to enqueue webhook delivery", error=str(e))
                
            # Publish to Redis for WebSocket In-App Notifications
            try:
                import json
                from backend.core.config import get_settings
                import redis.asyncio as aioredis
                
                settings = get_settings()
                channel_name = f"workspace:{tenant_id}:notifications"
                # We can't easily persist a single redis connection in the dispatcher without lifecycle management,
                # so we instantiate one briefly or use a global one. For simplicity in this publish method, we connect briefly.
                # In production, a singleton Redis pool should be used.
                redis_client = aioredis.from_url(settings.redis.redis_url)
                # Since publish is called in an async context, we must await it.
                # Wait, this is an async function, but we don't want to block publish. 
                # asyncio.create_task is safe here.
                async def _publish():
                    try:
                        await redis_client.publish(channel_name, json.dumps({
                            "type": event.event_type.value,
                            "payload": event_dict,
                            "timestamp": event_dict.get("occurred_at")
                        }))
                    finally:
                        await redis_client.aclose()
                asyncio.create_task(_publish())
            except Exception as e:
                logger.error("Failed to publish to Redis Pub/Sub", error=str(e))

        if not handlers:
            logger.debug(
                "Event published with no local subscribers",
                event_type=event.event_type,
                event_id=event.event_id,
            )
            return

        logger.debug(
            "Publishing event",
            event_type=event.event_type,
            event_id=event.event_id,
            subscriber_count=len(handlers),
        )

        results = await asyncio.gather(
            *(handler(event) for handler in handlers),
            return_exceptions=True,
        )

        for handler, result in zip(handlers, results, strict=True):
            if isinstance(result, Exception):
                logger.error(
                    "Event handler raised an exception",
                    event_type=event.event_type,
                    handler=handler.__qualname__,
                    error=str(result),
                    exc_info=result,
                )

    async def dispatch(self, event_type: "Any", payload: dict | None = None, **kwargs) -> None:
        """Backward compatibility shim for older codebase callers.

        Converts the older (event_type, payload) signature to a BaseEvent and routes
        it through the modern publish() method.
        """
        from backend.core.events.base import BaseEvent

        combined_payload = {}
        if payload:
            combined_payload.update(payload)
        combined_payload.update(kwargs)

        class LegacyEvent(BaseEvent):
            def __init__(self, etype, **kw):
                object.__setattr__(self, "event_type", etype)
                from datetime import datetime, UTC
                import uuid
                object.__setattr__(self, "event_id", str(uuid.uuid4()))
                object.__setattr__(self, "occurred_at", datetime.now(UTC))
                object.__setattr__(self, "correlation_id", None)
                for k, v in kw.items():
                    object.__setattr__(self, k, v)

        event = LegacyEvent(etype=event_type, **combined_payload)
        await self.publish(event)

    def handler_count(self, event_type: EventType) -> int:
        """Return the number of registered handlers for an event type."""
        return len(self._handlers.get(event_type, []))


# ── Application-level singleton ────────────────────────────────────────────────
# Imported and used by the application factory.
# Tests should create a fresh EventDispatcher() to avoid state leakage.

_dispatcher: EventDispatcher | None = None


def get_dispatcher() -> EventDispatcher:
    """Return the application-level event dispatcher singleton."""
    global _dispatcher  # noqa: PLW0603
    if _dispatcher is None:
        _dispatcher = EventDispatcher()
    return _dispatcher
