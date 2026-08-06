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
    """Sliding window rate limiter backed by Redis."""

    def __init__(self) -> None:
        self.redis: Redis = get_redis_client()

    async def check_rate_limit(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        tenant_limit: int = 60,
        user_limit: int = 20,
        window_seconds: int = 60
    ) -> None:
        """
        Enforce per-tenant and per-user request rate limits using a sliding window.
        """
        now = int(time.time())
        window_start = now - window_seconds

        tenant_key = f"raguard:{tenant_id}:ai:rate"
        user_key = f"raguard:{user_id}:ai:rate"

        async with self.redis.pipeline(transaction=True) as pipe:
            # Clean up old entries
            pipe.zremrangebyscore(tenant_key, 0, window_start)
            pipe.zremrangebyscore(user_key, 0, window_start)

            # Count current entries
            pipe.zcard(tenant_key)
            pipe.zcard(user_key)

            results = await pipe.execute()
            tenant_count = results[2]
            user_count = results[3]

        if tenant_count >= tenant_limit:
            logger.warning("Tenant rate limit exceeded", tenant_id=str(tenant_id), count=tenant_count)
            raise RateLimitExceededError("Tenant request rate limit exceeded.", retry_after=window_seconds)

        if user_count >= user_limit:
            logger.warning("User rate limit exceeded", user_id=str(user_id), count=user_count)
            raise RateLimitExceededError("User request rate limit exceeded.", retry_after=window_seconds)

        # Add new request
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.zadd(tenant_key, {str(uuid.uuid4()): now})
            pipe.expire(tenant_key, window_seconds)

            pipe.zadd(user_key, {str(uuid.uuid4()): now})
            pipe.expire(user_key, window_seconds)

            await pipe.execute()
