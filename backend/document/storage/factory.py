"""Storage Provider Factory.

Centralizes the initialization of the currently configured StorageProvider.
"""

import os

from backend.core.config import get_settings
from backend.document.storage.base import StorageProvider
from backend.document.storage.local import LocalStorageProvider


class StorageProviderFactory:
    """Factory for generating storage providers."""

    @classmethod
    def get_provider(cls) -> StorageProvider:
        """Return the active storage provider based on configuration."""
        settings = get_settings()
        provider_type = os.getenv("STORAGE_PROVIDER", "local").strip().lower()

        if provider_type in ("s3", "minio"):
            from backend.document.storage.cloud import S3StorageProvider
            bucket = os.getenv("S3_BUCKET_NAME") or os.getenv("AWS_S3_BUCKET_NAME") or "raguard-docs"
            region = os.getenv("AWS_REGION", "us-east-1")
            endpoint_url = os.getenv("S3_ENDPOINT_URL") or os.getenv("MINIO_ENDPOINT_URL")
            return S3StorageProvider(bucket=bucket, region=region, endpoint_url=endpoint_url)

        return LocalStorageProvider()
