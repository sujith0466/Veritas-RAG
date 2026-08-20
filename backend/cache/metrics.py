"""Redis Metrics Foundation.

Provides instrumentation hooks for cache observability.
These functions will eventually interface with the OpenTelemetry metrics API
(Epic 14). For now, they provide a standardized logging and counting interface.
"""

import structlog

logger = structlog.get_logger(__name__)

class RedisMetrics:
    """Singleton tracking Redis cache performance and health metrics."""

    _hits = 0
    _misses = 0
    _retries = 0
    _reconnects = 0

    @classmethod
    def record_hit(cls) -> None:
        """Record a cache hit."""
        cls._hits += 1
        try:
            from backend.observability.metrics.prometheus import record_redis_hit

            record_redis_hit()
        except Exception:
            pass

    @classmethod
    def record_miss(cls) -> None:
        """Record a cache miss."""
        cls._misses += 1
        try:
            from backend.observability.metrics.prometheus import record_redis_miss

            record_redis_miss()
        except Exception:
            pass

    @classmethod
    def record_retry(cls) -> None:
        """Record a connection or command retry attempt."""
        cls._retries += 1
        try:
            from backend.observability.metrics.prometheus import record_redis_retry

            record_redis_retry()
        except Exception:
            pass

    @classmethod
    def record_reconnect(cls) -> None:
        """Record a connection pool reconnect event."""
        cls._reconnects += 1
        try:
            from backend.observability.metrics.prometheus import record_redis_reconnect

            record_redis_reconnect()
        except Exception:
            pass

    @classmethod
    def get_stats(cls) -> dict[str, int]:
        """Return current metric counters."""
        return {
            "hits": cls._hits,
            "misses": cls._misses,
            "retries": cls._retries,
            "reconnects": cls._reconnects,
        }
