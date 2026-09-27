"""Unit tests for EventDispatcher Redis Pub/Sub publishing."""

import asyncio
from dataclasses import dataclass
from unittest.mock import AsyncMock, patch
import pytest

from backend.core.events.base import BaseEvent
from backend.core.events.dispatcher import EventDispatcher
from backend.core.events.types import EventType


@dataclass(frozen=True)
class DummyTenantEvent(BaseEvent):
    tenant_id: str = "tenant-123"
    document_id: str = "doc-456"
    data: dict = None


@pytest.mark.asyncio
async def test_dispatcher_publishes_to_redis_without_attribute_error():
    dispatcher = EventDispatcher()
    event = DummyTenantEvent(event_type=EventType.DOCUMENT_UPLOADED, tenant_id="tenant-123", data={"status": "success"})

    mock_redis_client = AsyncMock()
    mock_redis_client.publish = AsyncMock()
    mock_redis_client.aclose = AsyncMock()

    with patch("redis.asyncio.from_url", return_value=mock_redis_client) as mock_from_url, \
         patch("backend.tasks.webhooks.deliver_webhook_event_task.delay") as mock_webhook_delay:
        await dispatcher.publish(event)
        # Give async task time to execute
        await asyncio.sleep(0.05)

        # Verify from_url was called with the valid redis_url
        assert mock_from_url.called
        call_args = mock_from_url.call_args[0][0]
        assert call_args.startswith("redis://")

        # Verify publish was invoked on the tenant notification channel
        assert mock_redis_client.publish.called
        pub_channel = mock_redis_client.publish.call_args[0][0]
        assert pub_channel == "workspace:tenant-123:notifications"
