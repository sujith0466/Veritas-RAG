"""Embedding Provider Layer exports (`ADR-M2-001`)."""

from .base import BaseEmbeddingProvider, EmbeddingBatchResult
from .cohere_provider import CohereEmbeddingProvider
from .factory import EmbeddingProviderFactory, register_provider
from .local_provider import LocalEmbeddingProvider
from .manager import EmbeddingManager
from .openai_provider import OpenAIEmbeddingProvider

__all__ = [
    "BaseEmbeddingProvider",
    "CohereEmbeddingProvider",
    "EmbeddingBatchResult",
    "EmbeddingManager",
    "EmbeddingProviderFactory",
    "LocalEmbeddingProvider",
    "OpenAIEmbeddingProvider",
    "register_provider",
]
