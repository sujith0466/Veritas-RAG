"""Cache Abstraction Manager.

Provides generic infrastructure-level methods for caching operations.
Automatically enforces serialization, key namespaces, and TTL profiles.
"""

from typing import Any

from backend.cache.client import get_redis_client
from backend.cache.keys import CacheKeyBuilder, TTLProfile
from backend.cache.metrics import RedisMetrics
from backend.cache.serializers import CacheSerializer


class CacheManager:
    """Infrastructure-level manager for generic caching operations."""

    @classmethod
    async def get(
        cls, tenant: str, domain: str, entity: str, entity_id: str | Any
    ) -> Any | None:
        """Retrieve and deserialize a value from the cache."""
        key = CacheKeyBuilder.build(tenant, domain, entity, entity_id)
        client = get_redis_client()

        try:
            value = await client.get(key)
            if value is None:
                RedisMetrics.record_miss()
                return None

            RedisMetrics.record_hit()
            return CacheSerializer.deserialize(value)
        except Exception as e:
            RedisMetrics.record_retry()
            raise e

    @classmethod
    async def set(
        cls,
        tenant: str,
        domain: str,
        entity: str,
        entity_id: str | Any,
        value: Any,
        ttl: TTLProfile = TTLProfile.SHORT,
    ) -> None:
        """Serialize and store a value in the cache with a predefined TTL profile."""
        key = CacheKeyBuilder.build(tenant, domain, entity, entity_id)
        serialized_value = CacheSerializer.serialize(value)
        client = get_redis_client()

        try:
            await client.setex(key, int(ttl.value), serialized_value)
        except Exception as e:
            RedisMetrics.record_retry()
            raise e

    @classmethod
    async def delete(
        cls, tenant: str, domain: str, entity: str, entity_id: str | Any
    ) -> None:
        """Delete a key from the cache."""
        key = CacheKeyBuilder.build(tenant, domain, entity, entity_id)
        client = get_redis_client()

        try:
            await client.delete(key)
        except Exception as e:
            RedisMetrics.record_retry()
            raise e
