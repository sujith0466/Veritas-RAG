from backend.modules.storage.services.provider import StorageProvider, get_storage_provider


def get_current_storage_provider() -> StorageProvider:
    """FastAPI dependency for injecting the configured storage provider."""
    return get_storage_provider()
