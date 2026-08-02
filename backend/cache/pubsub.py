"""Pub/Sub Messaging Foundation.

Provides pure infrastructure primitives for real-time notifications
and transient event distribution. Does not contain business logic.
"""

from collections.abc import AsyncGenerator
from typing import Any

from backend.cache.client import get_redis_client
from backend.cache.keys import CacheKeyBuilder
from backend.cache.serializers import CacheSerializer


class PubSubManager:
    """Infrastructure-level manager for Pub/Sub messaging."""

    @classmethod
    async def publish(
        cls, tenant: str, domain: str, channel: str, message: Any
    ) -> int:
        """Publish a message to a structured channel.

        Args:
            tenant: Tenant identifier.
            domain: The system domain (e.g., 'notifications', 'chat').
            channel: The specific channel name.
            message: The payload to serialize and publish.

        Returns:
            The number of clients that received the message.
        """
        # We reuse the builder pattern for channel strings
        channel_name = CacheKeyBuilder.build(tenant, domain, "channel", channel)
        serialized_msg = CacheSerializer.serialize(message)
        client = get_redis_client()

        return await client.publish(channel_name, serialized_msg)

    @classmethod
    async def subscribe(
        cls, tenant: str, domain: str, channel: str
    ) -> AsyncGenerator[Any, None]:
        """Subscribe to a structured channel and yield messages.

        Args:
            tenant: Tenant identifier.
            domain: The system domain.
            channel: The specific channel name.

        Yields:
            Deserialized message payloads as they arrive.
        """
        channel_name = CacheKeyBuilder.build(tenant, domain, "channel", channel)
        client = get_redis_client()
        pubsub = client.pubsub()
        await pubsub.subscribe(channel_name)

        try:
            async for raw_message in pubsub.listen():
                if raw_message and raw_message.get("type") == "message":
                    data = raw_message.get("data")
                    if data:
                        yield CacheSerializer.deserialize(data)
        finally:
            await pubsub.unsubscribe(channel_name)
            await pubsub.close()
