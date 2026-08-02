"""Rate Limiting Foundation.

Provides infrastructure primitives for enforcing API quotas and rate limits
using Redis.
"""

from typing import Any

from backend.cache.client import get_redis_client
from backend.cache.keys import CacheKeyBuilder
from backend.core.exceptions.infrastructure import InfrastructureException


class RateLimitExceeded(InfrastructureException):
    """Raised when a rate limit is exceeded."""
    pass


class RateLimiter:
    """Infrastructure-level manager for rate limiting."""

    # Simple fixed-window rate limiter using INCR and EXPIRE
    _LUA_FIXED_WINDOW = """
    local current = redis.call("INCR", KEYS[1])
    if current == 1 then
        redis.call("EXPIRE", KEYS[1], ARGV[1])
    end
    return current
    """

    @classmethod
    async def check_limit(
        cls, tenant: str, domain: str, action: str, entity_id: str | Any, limit: int, window_seconds: int
    ) -> dict[str, int]:
        """Check if an action exceeds the rate limit in the given window.

        Args:
            tenant: Tenant identifier.
            domain: The system domain (e.g., 'api', 'auth').
            action: The specific action being limited (e.g., 'login_attempt').
            entity_id: The entity performing the action (e.g., IP address, user_id).
            limit: Maximum allowed requests within the window.
            window_seconds: The time window in seconds.

        Returns:
            A dictionary containing 'current', 'limit', and 'remaining'.

        Raises:
            RateLimitExceeded: If the current request exceeds the limit.
        """
        key = CacheKeyBuilder.build(tenant, domain, f"ratelimit:{action}", entity_id)
        client = get_redis_client()

        current = await client.eval(cls._LUA_FIXED_WINDOW, 1, key, window_seconds)

        remaining = max(0, limit - current)

        if current > limit:
            raise RateLimitExceeded(f"Rate limit exceeded for {action}")

        return {
            "current": current,
            "limit": limit,
            "remaining": remaining
        }
