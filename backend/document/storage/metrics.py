"""Storage Metrics Foundation.

Provides instrumentation hooks for Object Storage observability.
These functions will interface with OpenTelemetry metrics in Epic 14.
"""

import structlog

logger = structlog.get_logger(__name__)


class StorageMetrics:
    """Singleton tracking Storage performance and health metrics."""

    _upload_count = 0
    _download_count = 0
    _delete_count = 0
    _bytes_uploaded = 0
    _bytes_downloaded = 0
    _upload_latency = 0.0
    _download_latency = 0.0
    _retries = 0
    _failures = 0

    @classmethod
    def record_upload(cls, bytes_count: int, latency_ms: float) -> None:
        """Record a storage upload operation."""
        cls._upload_count += 1
        cls._bytes_uploaded += bytes_count
        cls._upload_latency += latency_ms
        try:
            from backend.observability.metrics.prometheus import record_storage_upload

            record_storage_upload(bytes_count, latency_ms / 1000.0)
        except Exception:
            pass

    @classmethod
    def record_download(cls, bytes_count: int, latency_ms: float) -> None:
        """Record a storage download operation."""
        cls._download_count += 1
        cls._bytes_downloaded += bytes_count
        cls._download_latency += latency_ms
        try:
            from backend.observability.metrics.prometheus import record_storage_download

            record_storage_download(bytes_count, latency_ms / 1000.0)
        except Exception:
            pass

    @classmethod
    def record_delete(cls) -> None:
        """Record a storage deletion operation."""
        cls._delete_count += 1
        try:
            from backend.observability.metrics.prometheus import record_storage_delete

            record_storage_delete()
        except Exception:
            pass

    @classmethod
    def record_retry(cls) -> None:
        """Record a transient network retry attempt."""
        cls._retries += 1

    @classmethod
    def record_failure(cls) -> None:
        """Record an infrastructure or validation failure."""
        cls._failures += 1
        try:
            from backend.observability.metrics.prometheus import record_storage_failure

            record_storage_failure("general")
        except Exception:
            pass

    @classmethod
    def get_stats(cls) -> dict[str, float]:
        """Return current metric counters and averages."""
        avg_upload = cls._upload_latency / cls._upload_count if cls._upload_count > 0 else 0.0
        avg_download = cls._download_latency / cls._download_count if cls._download_count > 0 else 0.0

        return {
            "upload_count": cls._upload_count,
            "download_count": cls._download_count,
            "delete_count": cls._delete_count,
            "bytes_uploaded": cls._bytes_uploaded,
            "bytes_downloaded": cls._bytes_downloaded,
            "avg_upload_latency_ms": round(avg_upload, 2),
            "avg_download_latency_ms": round(avg_download, 2),
            "retries": cls._retries,
            "failures": cls._failures,
        }
