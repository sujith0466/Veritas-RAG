"""Storage Utility functions including bucket naming and validation."""

from typing import Any

from backend.core.config import get_settings


class BucketNameBuilder:
    """Centralizes bucket naming strategy for Object Storage."""

    @classmethod
    def build_document_bucket(cls) -> str:
        """Get the bucket name for raw document artifacts."""
        settings = get_settings()
        # Default fallback if not defined
        return getattr(settings, "storage_document_bucket", "raguard-documents")

    @classmethod
    def build_audit_bucket(cls) -> str:
        """Get the bucket name for WORM-compliant audit logs."""
        settings = get_settings()
        return getattr(settings, "storage_audit_bucket", "raguard-audit-logs")


async def check_storage_health() -> dict[str, Any]:
    """Check Object Storage connectivity and measure latency.

    Returns detailed connection status, latency in ms, and provider info.
    """
    import time

    import structlog

    from backend.document.storage.factory import StorageProviderFactory
    from backend.document.storage.metrics import StorageMetrics

    logger = structlog.get_logger(__name__)
    start = time.perf_counter()
    status = "healthy"
    error = None
    provider_name = None
    bucket_name = None

    try:
        provider = StorageProviderFactory.get_provider()
        provider_name = provider.provider_name
        bucket_name = provider.bucket_name

        # Checking if a dummy object exists validates connectivity, credentials, and bucket access.
        await provider.object_exists("health-check-dummy-key")

    except Exception as exc:
        logger.warning("Object storage health check failed", error=str(exc))
        StorageMetrics.record_failure()
        status = "unhealthy"
        error = str(exc)

    latency_ms = (time.perf_counter() - start) * 1000
    stats = StorageMetrics.get_stats()

    return {
        "status": status,
        "latency_ms": round(latency_ms, 2),
        "provider": provider_name,
        "bucket": bucket_name,
        "retries": stats.get("retries", 0),
        "errors": stats.get("failures", 0),
        "error": error
    }
