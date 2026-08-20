"""Vector DB Metrics Foundation.

Provides instrumentation hooks for Qdrant vector search observability.
These functions will eventually interface with the OpenTelemetry metrics API
(Epic 14). For now, they provide a standardized logging and counting interface.
"""

import structlog

logger = structlog.get_logger(__name__)


class QdrantMetrics:
    """Singleton tracking Qdrant performance and health metrics."""

    _searches = 0
    _search_latency = 0.0
    _upserts = 0
    _upsert_latency = 0.0
    _collection_creations = 0
    _payload_index_creations = 0
    _retries = 0
    _errors = 0

    @classmethod
    def record_search(cls, latency_ms: float) -> None:
        """Record a dense search operation and its latency."""
        cls._searches += 1
        cls._search_latency += latency_ms
        try:
            from backend.observability.metrics.prometheus import record_qdrant_search

            record_qdrant_search(latency_ms / 1000.0)
        except Exception:
            pass

    @classmethod
    def record_upsert(cls, latency_ms: float) -> None:
        """Record a batch upsert operation and its latency."""
        cls._upserts += 1
        cls._upsert_latency += latency_ms
        try:
            from backend.observability.metrics.prometheus import record_qdrant_upsert

            record_qdrant_upsert(latency_ms / 1000.0)
        except Exception:
            pass

    @classmethod
    def record_collection_creation(cls) -> None:
        """Record a collection creation event."""
        cls._collection_creations += 1

    @classmethod
    def record_payload_index_creation(cls) -> None:
        """Record a payload index creation event."""
        cls._payload_index_creations += 1

    @classmethod
    def record_retry(cls) -> None:
        """Record a transient connection or command retry attempt."""
        cls._retries += 1

    @classmethod
    def record_error(cls) -> None:
        """Record an infrastructure or validation error."""
        cls._errors += 1
        try:
            from backend.observability.metrics.prometheus import record_qdrant_error

            record_qdrant_error("general")
        except Exception:
            pass

    @classmethod
    def get_stats(cls) -> dict[str, float]:
        """Return current metric counters and averages."""
        avg_search = cls._search_latency / cls._searches if cls._searches > 0 else 0.0
        avg_upsert = cls._upsert_latency / cls._upserts if cls._upserts > 0 else 0.0

        return {
            "searches": cls._searches,
            "avg_search_latency_ms": round(avg_search, 2),
            "upserts": cls._upserts,
            "avg_upsert_latency_ms": round(avg_upsert, 2),
            "collection_creations": cls._collection_creations,
            "payload_index_creations": cls._payload_index_creations,
            "retries": cls._retries,
            "errors": cls._errors,
        }
