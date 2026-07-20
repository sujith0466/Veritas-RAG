"""Base Embedding Provider Interface (`BaseEmbeddingProvider`).

Defines the contractual abstraction required for all concrete embedding providers (`OpenAI`, `Cohere`, `Local`),
enforcing asynchronous vector generation, dimension checking, and token usage accounting.
"""

from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel, Field


class EmbeddingBatchResult(BaseModel):
    """Result payload returned by provider batch vectorization."""

    embeddings: list[list[float]] = Field(description="List of floating point dense vector arrays")
    tokens_consumed: int = Field(default=0, description="Total tokens billed or processed during generation")
    provider_metadata: dict[str, Any] = Field(default_factory=dict, description="Additional provider response metadata")


class BaseEmbeddingProvider(ABC):
    """Abstract base class for all embedding providers."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the vector dimensionality (e.g., 1536 for text-embedding-3-large)."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the exact model identifier (e.g., 'text-embedding-3-large')."""
        pass

    @abstractmethod
    async def embed_documents(self, texts: list[str]) -> EmbeddingBatchResult:
        """Generate dense embedding vectors for a batch of input strings.

        Args:
            texts: List of input string chunks.

        Returns:
            EmbeddingBatchResult containing the vector arrays and total tokens consumed.
        """
        pass

    @abstractmethod
    async def embed_query(self, text: str) -> list[float]:
        """Generate a single dense vector embedding for a search or validation query.

        Args:
            text: Query text.

        Returns:
            Single float array vector matching self.dimension.
        """
        pass
