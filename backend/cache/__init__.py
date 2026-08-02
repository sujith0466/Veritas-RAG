"""Caching infrastructure module (`backend/cache/`)."""

from .client import check_cache_health, close_cache, get_cache, get_redis_client, get_redis_pool

__all__ = [
    "check_cache_health",
    "close_cache",
    "get_cache",
    "get_redis_client",
    "get_redis_pool",
]
