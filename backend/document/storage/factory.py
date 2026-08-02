"""Storage Provider Factory.

Centralizes the initialization of the currently configured StorageProvider.
"""

from backend.core.config import get_settings
from backend.document.storage.base import StorageProvider
from backend.document.storage.local import LocalStorageProvider

# We will add cloud providers here in subsequent tasks

class StorageProviderFactory:
    """Factory for generating storage providers."""

    @classmethod
    def get_provider(cls) -> StorageProvider:
        """Return the active storage provider based on configuration."""
        settings = get_settings()

        # Currently defaults to LocalStorageProvider for isolated development
        # and tests unless explicit cloud configuration is provided.
        # This will be expanded in F1.5 Task 4 (S3StorageProvider)
        return LocalStorageProvider()
