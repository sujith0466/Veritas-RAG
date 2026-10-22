import time
import uuid

from redis.asyncio import Redis
import structlog

from backend.cache.client import get_redis_client
from backend.core.exceptions import RateLimitException

logger = structlog.get_logger(__name__)


class RateLimitExceededError(RateLimitException):
    def __init__(self, message: str, retry_after: int):
        super().__init__(message=message)
        self.retry_after = retry_after


class RateLimiter:
    """Atomic sliding window rate limiter backed by Redis Lua script."""

    # Atomic multi-key sliding window check-and-insert script
    _LUA_ATOMIC_CHECK_AND_ADD = """
    local tenant_key = KEYS[1]
    local user_key = KEYS[2]
    local now = tonumber(ARGV[1])
    local window = tonumber(ARGV[2])
    local tenant_limit = tonumber(ARGV[3])
    local user_limit = tonumber(ARGV[4])
    local member = ARGV[5]
    local window_start = now - window

    -- 1. Clean up old entries
    redis.call('ZREMRANGEBYSCORE', tenant_key, '-inf', window_start)
    redis.call('ZREMRANGEBYSCORE', user_key, '-inf', window_start)

    -- 2. Check counts
    local tenant_count = redis.call('ZCARD', tenant_key)
    if tenant_count >= tenant_limit then
        local oldest = redis.call('ZRANGE', tenant_key, 0, 0, 'WITHSCORES')
        local retry_after = window
        if #oldest > 1 then
            retry_after = math.max(1, math.ceil((tonumber(oldest[2]) + window) - now))
        end
        return {0, 'tenant', retry_after}
    end

    local user_count = redis.call('ZCARD', user_key)
    if user_count >= user_limit then
        local oldest = redis.call('ZRANGE', user_key, 0, 0, 'WITHSCORES')
        local retry_after = window
        if #oldest > 1 then
            retry_after = math.max(1, math.ceil((tonumber(oldest[2]) + window) - now))
        end
        return {0, 'user', retry_after}
    end

    -- 3. Atomically add new request to both sorted sets
    redis.call('ZADD', tenant_key, now, member)
    redis.call('EXPIRE', tenant_key, math.ceil(window) + 1)

    redis.call('ZADD', user_key, now, member)
    redis.call('EXPIRE', user_key, math.ceil(window) + 1)

    return {1, 'ok', 0}
    """

    def __init__(self) -> None:
        self.redis: Redis = get_redis_client()

    async def check_rate_limit(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        tenant_limit: int = 60,
        user_limit: int = 20,
        window_seconds: int = 60,
    ) -> None:
        """
        Enforce per-tenant and per-user request rate limits atomically using a sliding window.
        """
        now = time.time()
        tenant_key = f"raguard:{tenant_id}:ai:rate"
        user_key = f"raguard:{user_id}:ai:rate"
        member = f"{now}:{uuid.uuid4().hex[:8]}"

        try:
            result = await self.redis.eval(
                self._LUA_ATOMIC_CHECK_AND_ADD,
                2,
                tenant_key,
                user_key,
                str(now),
                str(window_seconds),
                str(tenant_limit),
                str(user_limit),
                member,
            )

            # result format: [allowed (1 or 0), reason ('ok', 'tenant', 'user'), retry_after]
            allowed = bool(result[0])
            reason = str(result[1])
            retry_after = int(result[2])

            if not allowed:
                if reason == "tenant":
                    logger.warning("Tenant rate limit exceeded", tenant_id=str(tenant_id))
                    raise RateLimitExceededError("Tenant request rate limit exceeded.", retry_after=retry_after)
                else:
                    logger.warning("User rate limit exceeded", user_id=str(user_id))
                    raise RateLimitExceededError("User request rate limit exceeded.", retry_after=retry_after)

        except RateLimitExceededError:
            raise
        except Exception as exc:
            logger.error("Error evaluating AI rate limit", error=str(exc))
            # Fail-open for AI wrapper generation
            return
