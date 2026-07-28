"""Embedding Provider Factory (`EmbeddingProviderFactory`).

Dynamically resolves and instantiates concrete embedding providers (`OpenAI`, `Cohere`, `Local`)
based on tenant configuration and request overrides (`ADR-M2-001`).
"""

from typing import Any

import structlog

from backend.modules.embedding.providers.base import BaseEmbeddingProvider
from backend.modules.embedding.schemas.embedding_dto import (
    ProviderInfoDTO, ProviderModelInfoDTO)
from backend.modules.embedding.schemas.errors import (EmbeddingDomainException,
                                                      EmbeddingErrorCode)

logger = structlog.get_logger(__name__)


# Registry mapping provider codes to provider classes or factories.
# Concrete provider implementations (OpenAI, Cohere, Local) are registered in Milestone C.
_PROVIDER_REGISTRY: dict[str, type[BaseEmbeddingProvider] | Any] = {}
_PROVIDER_INSTANCES: dict[str, BaseEmbeddingProvider] = {}
import threading
_FACTORY_LOCK = threading.Lock()


def register_provider(
    name: str, provider_cls: type[BaseEmbeddingProvider] | Any
) -> None:
    """Register a concrete provider implementation with the factory."""
    _PROVIDER_REGISTRY[name.lower()] = provider_cls


class EmbeddingProviderFactory:
    """Factory responsible for instantiating and resolving embedding providers."""

    @classmethod
    def get_provider(
        cls,
        provider_name: str | None = None,
        model_name: str | None = None,
        api_key: str | None = None,
    ) -> BaseEmbeddingProvider:
        """Resolve and return an instance of `BaseEmbeddingProvider`.

        Args:
            provider_name: Target provider code ('openai', 'cohere', 'local').
            model_name: Optional specific model identifier.
            api_key: Optional tenant-scoped or override API key.

        Returns:
            Configured `BaseEmbeddingProvider` instance.

        Raises:
            EmbeddingDomainException (`EMB_001` or `EMB_005`) if provider is unsupported or uninitialized.
        """
        # Default to 'openai' if not specified (checked against settings in service layer)
        target_provider = (provider_name or "openai").lower()
        
        # Build a unique cache key based on provider configuration
        cache_key = f"{target_provider}::{model_name}::{api_key}"

        with _FACTORY_LOCK:
            if cache_key in _PROVIDER_INSTANCES:
                return _PROVIDER_INSTANCES[cache_key]

            provider_cls = _PROVIDER_REGISTRY.get(target_provider)
            if not provider_cls:
                raise EmbeddingDomainException(
                    code=EmbeddingErrorCode.EMB_001,
                    message=f"Embedding provider '{target_provider}' is not registered or supported.",
                    detail={
                        "requested_provider": target_provider,
                        "available_providers": list(_PROVIDER_REGISTRY.keys()),
                    },
                )

            try:
                instance = provider_cls(model_name=model_name, api_key=api_key)
                _PROVIDER_INSTANCES[cache_key] = instance
                return instance
            except Exception as exc:
                logger.error(
                    "provider_instantiation_failed",
                    provider=target_provider,
                    error=str(exc),
                )
                raise EmbeddingDomainException(
                    code=EmbeddingErrorCode.EMB_005,
                    message=f"Failed to initialize embedding provider '{target_provider}': {exc}",
                    detail={"provider": target_provider, "error": str(exc)},
                )

    @classmethod
    def list_available_providers(cls) -> list[ProviderInfoDTO]:
        """Return the catalog of supported embedding providers and their models."""
        return [
            ProviderInfoDTO(
                provider="openai",
                display_name="OpenAI Embeddings",
                description="High-accuracy cloud dense embeddings with native 1536-dimensional representation.",
                is_available="openai" in _PROVIDER_REGISTRY,
                models=[
                    ProviderModelInfoDTO(
                        model_name="text-embedding-3-large",
                        dimension=1536,
                        max_input_tokens=8191,
                        is_default=True,
                    ),
                    ProviderModelInfoDTO(
                        model_name="text-embedding-3-small",
                        dimension=1536,
                        max_input_tokens=8191,
                        is_default=False,
                    ),
                ],
            ),
            ProviderInfoDTO(
                provider="cohere",
                display_name="Cohere Embeddings",
                description="Enterprise multilingual dense embeddings optimized for cross-language search.",
                is_available="cohere" in _PROVIDER_REGISTRY,
                models=[
                    ProviderModelInfoDTO(
                        model_name="embed-multilingual-v3.0",
                        dimension=1024,
                        max_input_tokens=512,
                        is_default=True,
                    ),
                ],
            ),
            ProviderInfoDTO(
                provider="local",
                display_name="Local HuggingFace / ONNX Embeddings",
                description="Self-hosted, air-gapped dense vectorization using local sentence-transformers / BGE.",
                is_available="local" in _PROVIDER_REGISTRY,
                models=[
                    ProviderModelInfoDTO(
                        model_name="BAAI/bge-large-en-v1.5",
                        dimension=1024,
                        max_input_tokens=512,
                        is_default=True,
                    ),
                ],
            ),
        ]
