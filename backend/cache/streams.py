"""Streams Messaging Foundation.

Provides pure infrastructure primitives for reliable event logs and messaging
using Redis Streams. Does not contain business logic.
"""

from typing import Any

from backend.cache.client import get_redis_client
from backend.cache.keys import CacheKeyBuilder
from backend.cache.serializers import CacheSerializer


class StreamManager:
    """Infrastructure-level manager for Redis Streams."""

    @classmethod
    async def xadd(
        cls, tenant: str, domain: str, stream_name: str, payload: dict[str, Any], max_len: int = 10000
    ) -> str:
        """Add an event to a Redis Stream.

        Args:
            tenant: Tenant identifier.
            domain: The system domain (e.g., 'audit', 'jobs').
            stream_name: The specific stream name.
            payload: A dictionary of key-value pairs to add.
            max_len: Maximum length of the stream (approximate).

        Returns:
            The generated message ID.
        """
        stream_key = CacheKeyBuilder.build(tenant, domain, "stream", stream_name)

        # Serialize payload values to string
        serialized_payload = {
            k: CacheSerializer.serialize(v) for k, v in payload.items()
        }

        client = get_redis_client()
        return await client.xadd(stream_key, serialized_payload, maxlen=max_len, approximate=True)

    @classmethod
    async def xread(
        cls, tenant: str, domain: str, stream_name: str, last_id: str = "0-0", count: int = 10, block: int | None = None
    ) -> list[tuple[str, dict[str, Any]]]:
        """Read events from a Redis Stream.

        Args:
            tenant: Tenant identifier.
            domain: The system domain.
            stream_name: The specific stream name.
            last_id: The ID to read after.
            count: Maximum number of messages to return.
            block: Blocking timeout in milliseconds.

        Returns:
            A list of tuples containing the message ID and the deserialized payload dictionary.
        """
        stream_key = CacheKeyBuilder.build(tenant, domain, "stream", stream_name)
        client = get_redis_client()

        streams = {stream_key: last_id}
        result = await client.xread(streams, count=count, block=block)

        parsed_messages = []
        if not result:
            return parsed_messages

        # result format: [[b'stream_name', [(b'message_id', {b'key': b'value'})]]]
        for stream_data in result:
            if stream_data[0].decode("utf-8") == stream_key:
                messages = stream_data[1]
                for msg_id, raw_payload in messages:
                    decoded_payload = {
                        k.decode("utf-8"): CacheSerializer.deserialize(v)
                        for k, v in raw_payload.items()
                    }
                    parsed_messages.append((msg_id.decode("utf-8"), decoded_payload))

        return parsed_messages
