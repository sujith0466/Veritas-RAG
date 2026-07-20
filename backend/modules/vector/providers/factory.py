"""Factory for vector database providers (`ADR-004`).

Resolves and returns the configured concrete `BaseVectorDBProvider` instance,
defaulting to self-hosted Qdrant (`QdrantVectorDBProvider`).
"""

import structlog
from qdrant_client import AsyncQdrantClient

from backend.modules.vector.providers.base import BaseVectorDBProvider
from backend.modules.vector.providers.qdrant_provider import QdrantVectorDBProvider

logger = structlog.get_logger(__name__)


class VectorProviderFactory:
    """Factory creating and caching vector database provider instances (`ADR-004`)."""

    _cached_provider: BaseVectorDBProvider | None = None

    @classmethod
    def get_provider(
        cls,
        provider_name: str = "qdrant",
        client: AsyncQdrantClient | None = None,
        force_refresh: bool = False,
    ) -> BaseVectorDBProvider:
        """Resolve and return a vector database provider instance."""
        if cls._cached_provider is not None and not force_refresh and client is None:
            return cls._cached_provider

        name_lower = provider_name.strip().lower()
        if name_lower == "qdrant":
            provider = QdrantVectorDBProvider(client=client)
            if client is None:
                cls._cached_provider = provider
            return provider

        raise ValueError(f"Unsupported vector database provider engine: '{provider_name}'.")

    @classmethod
    def clear_cache(cls) -> None:
        """Clear cached provider instances (used during testing or configuration resets)."""
        cls._cached_provider = None
