"""Redis Cache Client and Connection Management.

Provides async connection pooling, Redis client singleton, and health checking
for distributed caching, rate limiting, and session state.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog
from redis.asyncio import ConnectionPool, Redis
from redis.exceptions import ConnectionError, TimeoutError

from backend.cache.metrics import RedisMetrics
from backend.core.config import get_settings
from backend.core.utils.retry import with_retry
import time

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

logger = structlog.get_logger(__name__)


class _CacheState:
    pool: ConnectionPool[Any] | None = None
    client: Redis[Any] | None = None


_state = _CacheState()


def get_redis_pool() -> ConnectionPool[Any]:
    """Return the singleton Redis ConnectionPool instance, creating it if needed."""
    if _state.pool is not None:
        return _state.pool

    settings = get_settings()
    url = settings.redis.test_url if settings.is_testing else settings.redis.url

    logger.info("Initializing Redis connection pool")
    _state.pool = ConnectionPool.from_url(
        url,
        max_connections=settings.redis.max_connections,
        socket_timeout=settings.redis.socket_timeout,
        decode_responses=True,
    )
    return _state.pool


def get_redis_client() -> Redis[Any]:
    """Return the singleton async Redis client instance."""
    if _state.client is not None:
        return _state.client

    pool = get_redis_pool()
    _state.client = Redis(connection_pool=pool)
    return _state.client


async def get_cache() -> AsyncGenerator[Redis[Any], None]:
    """FastAPI dependency yielding the async Redis client."""
    yield get_redis_client()


async def check_cache_health() -> dict[str, Any]:
    """Check Redis connectivity by executing PING and measure latency.
    
    Returns detailed connection status, latency in ms, and reconnect metrics.
    """
    start = time.perf_counter()
    status = "healthy"
    error = None
    
    try:
        # Wrap ping with retry to evaluate transient connectivity
        @with_retry(max_retries=2, base_delay=0.1, exceptions=(ConnectionError, TimeoutError))
        async def _ping():
            client = get_redis_client()
            return await client.ping()
            
        result = await _ping()
        if result is not True and str(result) != "PONG":
            status = "unhealthy"
            error = "Invalid PING response"
    except Exception as exc:
        logger.warning("Redis health check failed", error=str(exc))
        status = "unhealthy"
        error = str(exc)
        
    latency_ms = (time.perf_counter() - start) * 1000
    stats = RedisMetrics.get_stats()
    
    return {
        "status": status,
        "latency_ms": round(latency_ms, 2),
        "reconnects": stats["reconnects"],
        "retries": stats["retries"],
        "error": error
    }


async def close_cache() -> None:
    """Close the Redis client and disconnect the connection pool."""
    if _state.client is not None:
        logger.info("Closing async Redis client")
        await _state.client.close()
        _state.client = None

    if _state.pool is not None:
        logger.info("Disconnecting Redis connection pool")
        await _state.pool.disconnect()
        _state.pool = None
