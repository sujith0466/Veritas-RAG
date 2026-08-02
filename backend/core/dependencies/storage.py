from backend.document.storage.base import StorageProvider
from backend.document.storage.factory import StorageProviderFactory


def get_current_storage_provider() -> StorageProvider:
    """FastAPI dependency for injecting the configured storage provider."""
    return StorageProviderFactory.get_provider()
