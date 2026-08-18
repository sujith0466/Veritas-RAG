"""Redis Cache Client and Connection Management.

Provides async connection pooling, Redis client singleton, and health checking
for distributed caching, rate limiting, and session state.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any
import weakref

from redis.asyncio import ConnectionPool, Redis
from redis.exceptions import ConnectionError, TimeoutError
import structlog

from backend.cache.metrics import RedisMetrics
from backend.core.config import get_settings
from backend.core.utils.retry import with_retry

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

logger = structlog.get_logger(__name__)


class _CacheState:
    pools: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
    clients: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
    fallback_pool: ConnectionPool[Any] | None = None
    fallback_client: Redis[Any] | None = None


_state = _CacheState()


def get_redis_pool() -> ConnectionPool[Any]:
    """Return the Redis ConnectionPool instance, isolated per event loop."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None:
        if loop in _state.pools:
            return _state.pools[loop]
    elif _state.fallback_pool is not None:
        return _state.fallback_pool

    settings = get_settings()
    url = settings.redis.test_url if settings.is_testing else settings.redis.url

    logger.info("Initializing Redis connection pool", loop_id=id(loop) if loop else 0)
    pool = ConnectionPool.from_url(
        url,
        max_connections=settings.redis.max_connections,
        socket_timeout=settings.redis.socket_timeout,
        decode_responses=True,
    )
    if loop is not None:
        _state.pools[loop] = pool
    else:
        _state.fallback_pool = pool
    return pool


def get_redis_client() -> Redis[Any]:
    """Return the async Redis client instance, isolated per event loop."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None:
        if loop in _state.clients:
            return _state.clients[loop]
    elif _state.fallback_client is not None:
        return _state.fallback_client

    pool = get_redis_pool()
    client = Redis(connection_pool=pool)
    if loop is not None:
        _state.clients[loop] = client
    else:
        _state.fallback_client = client
    return client


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
    for loop, client in list(_state.clients.items()):
        try:
            await client.close()
        except Exception:
            pass
    _state.clients.clear()

    for loop, pool in list(_state.pools.items()):
        try:
            await pool.disconnect()
        except Exception:
            pass
    _state.pools.clear()

    if _state.fallback_client:
        try:
            await _state.fallback_client.close()
        except Exception:
            pass
        _state.fallback_client = None

    if _state.fallback_pool:
        try:
            await _state.fallback_pool.disconnect()
        except Exception:
            pass
        _state.fallback_pool = None
