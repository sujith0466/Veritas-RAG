"""Rate Limiting Foundation.

Provides infrastructure primitives for enforcing API quotas and rate limits
using Redis with atomic sliding-window Lua execution and endpoint-specific
degradation policies.
"""

import math
import time
import uuid
from typing import Any
import structlog

from backend.cache.client import get_redis_client
from backend.cache.keys import CacheKeyBuilder
from backend.core.exceptions.infrastructure import InfrastructureException

logger = structlog.get_logger(__name__)


class RateLimitExceeded(InfrastructureException):
    """Raised when a rate limit is exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: int = 1,
        limit: int = 60,
        remaining: int = 0,
        reset_seconds: int = 1,
    ) -> None:
        super().__init__(message)
        self.retry_after = retry_after
        self.limit = limit
        self.remaining = remaining
        self.reset_seconds = reset_seconds


class RateLimiter:
    """Infrastructure-level manager for rate limiting."""

    # Atomic sliding-window rate limiter using Redis sorted sets (ZSET)
    # KEYS[1]: rate limit key
    # ARGV[1]: current timestamp in seconds (float or int)
    # ARGV[2]: window duration in seconds
    # ARGV[3]: max allowed requests (limit)
    # ARGV[4]: unique member identifier (timestamp:uuid)
    # Returns: {allowed (1 or 0), remaining, retry_after}
    _LUA_SLIDING_WINDOW = """
    local key = KEYS[1]
    local now = tonumber(ARGV[1])
    local window = tonumber(ARGV[2])
    local limit = tonumber(ARGV[3])
    local member = ARGV[4]
    local clear_before = now - window

    -- 1. Remove expired timestamps outside the current sliding window
    redis.call('ZREMRANGEBYSCORE', key, '-inf', clear_before)

    -- 2. Count requests in active sliding window
    local current_count = redis.call('ZCARD', key)

    if current_count < limit then
        -- 3. Add current request
        redis.call('ZADD', key, now, member)
        redis.call('EXPIRE', key, math.ceil(window) + 1)
        return {1, limit - current_count - 1, 0}
    else
        -- 4. Calculate exact retry_after from the oldest request within the window
        local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
        local retry_after = 1
        if #oldest > 1 then
            local oldest_ts = tonumber(oldest[2])
            retry_after = math.max(1, math.ceil((oldest_ts + window) - now))
        end
        return {0, 0, retry_after}
    end
    """

    @classmethod
    async def check_limit(
        cls,
        tenant: str,
        domain: str,
        action: str,
        entity_id: str | Any,
        limit: int,
        window_seconds: int,
        degradation_policy: str = "fail_open",
    ) -> dict[str, int]:
        """Check if an action exceeds the rate limit in the given sliding window.

        Args:
            tenant: Tenant identifier.
            domain: The system domain (e.g., 'api', 'auth', 'chat', 'documents').
            action: The specific action being limited (e.g., 'login', 'upload').
            entity_id: The entity performing the action (e.g., IP address, user_id).
            limit: Maximum allowed requests within the window.
            window_seconds: The time window in seconds.
            degradation_policy: 'fail_open' or 'fail_closed' if Redis is unavailable.

        Returns:
            A dictionary containing 'current', 'limit', 'remaining', and 'reset_seconds'.

        Raises:
            RateLimitExceeded: If the current request exceeds the limit,
                               or if Redis is unavailable under fail_closed policy.
        """
        key = CacheKeyBuilder.build(tenant, domain, f"ratelimit:{action}", entity_id)
        now = time.time()
        member = f"{now}:{uuid.uuid4().hex[:8]}"

        try:
            client = get_redis_client()
            result = await client.eval(
                cls._LUA_SLIDING_WINDOW,
                1,
                key,
                str(now),
                str(window_seconds),
                str(limit),
                member,
            )

            # result format: [allowed (1 or 0), remaining, retry_after]
            allowed = bool(result[0])
            remaining = int(result[1])
            retry_after = int(result[2])
            reset_seconds = retry_after if retry_after > 0 else window_seconds

            if not allowed:
                raise RateLimitExceeded(
                    message=f"Rate limit exceeded for {action}. Try again in {retry_after}s.",
                    retry_after=retry_after,
                    limit=limit,
                    remaining=0,
                    reset_seconds=reset_seconds,
                )

            return {
                "current": limit - remaining,
                "limit": limit,
                "remaining": remaining,
                "reset_seconds": window_seconds,
            }

        except RateLimitExceeded:
            raise
        except Exception as exc:
            # Redis connection or execution failure (GAP-RAT-05)
            logger.error(
                "rate_limit_redis_failure",
                severity="HIGH",
                action=action,
                domain=domain,
                policy=degradation_policy,
                error=str(exc),
            )
            try:
                from backend.observability.metrics.prometheus import RATE_LIMIT_REDIS_FAILURES_TOTAL
                RATE_LIMIT_REDIS_FAILURES_TOTAL.labels(action=action, domain=domain, policy=degradation_policy).inc()
            except Exception:
                pass

            if degradation_policy == "fail_closed":
                raise RateLimitExceeded(
                    message="Service temporarily unavailable due to rate limiter outage. Please retry shortly.",
                    retry_after=30,
                    limit=limit,
                    remaining=0,
                    reset_seconds=30,
                ) from exc

            # fail_open: permit request through with fallback telemetry
            return {
                "current": 0,
                "limit": limit,
                "remaining": limit,
                "reset_seconds": window_seconds,
                "degraded": True,
            }
