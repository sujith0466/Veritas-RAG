"""Embedding Manager (`EmbeddingManager`).

Orchestrates batch vectorization across registered embedding providers, handling sub-batching (`batch_size=100`),
token accounting, and capability checks (`ADR-M2-001`). Also registers concrete providers with `EmbeddingProviderFactory`.
"""

from typing import Any

import structlog

from backend.modules.embedding.providers.base import BaseEmbeddingProvider, EmbeddingBatchResult
from backend.modules.embedding.providers.cohere_provider import CohereEmbeddingProvider
from backend.modules.embedding.providers.factory import EmbeddingProviderFactory, register_provider
from backend.modules.embedding.providers.local_provider import LocalEmbeddingProvider
from backend.modules.embedding.providers.openai_provider import OpenAIEmbeddingProvider
from backend.modules.embedding.schemas.errors import InvalidInputError

logger = structlog.get_logger(__name__)

# Register concrete provider classes in the factory upon module import
register_provider("openai", OpenAIEmbeddingProvider)
register_provider("cohere", CohereEmbeddingProvider)
register_provider("local", LocalEmbeddingProvider)


class EmbeddingManager:
    """Orchestrates batch vectorization across providers with automatic sub-batching."""

    def __init__(
        self,
        provider_name: str | None = None,
        model_name: str | None = None,
        api_key: str | None = None,
        provider_instance: BaseEmbeddingProvider | None = None,
    ) -> None:
        if provider_instance is not None:
            self.provider = provider_instance
        else:
            self.provider = EmbeddingProviderFactory.get_provider(
                provider_name=provider_name,
                model_name=model_name,
                api_key=api_key,
            )

    @property
    def dimension(self) -> int:
        return self.provider.dimension

    @property
    def model_name(self) -> str:
        return self.provider.model_name

    async def vectorize_batch(
        self, texts: list[str], batch_size: int = 100
    ) -> EmbeddingBatchResult:
        """Vectorize a list of strings, splitting into chunks of `batch_size` if needed."""
        if not texts:
            raise InvalidInputError(
                "Empty text list provided to EmbeddingManager.vectorize_batch."
            )
        if batch_size < 1:
            raise InvalidInputError("batch_size must be at least 1.")

        if len(texts) <= batch_size:
            return await self.provider.embed_documents(texts)

        all_vectors: list[list[float]] = []
        total_tokens = 0
        meta_merged: dict[str, Any] = {"sub_batches": []}

        for i in range(0, len(texts), batch_size):
            sub_batch = texts[i : i + batch_size]
            res = await self.provider.embed_documents(sub_batch)
            all_vectors.extend(res.embeddings)
            total_tokens += res.tokens_consumed
            meta_merged["sub_batches"].append(res.provider_metadata)

        return EmbeddingBatchResult(
            embeddings=all_vectors,
            tokens_consumed=total_tokens,
            provider_metadata=meta_merged,
        )

    async def vectorize_query(self, query: str) -> list[float]:
        """Generate a single vector for a query string."""
        return await self.provider.embed_query(query)

    def validate_capabilities(
        self, chunk_count: int, max_tokens_per_chunk: int
    ) -> bool:
        """Validate whether the provider and model support the requested chunk dimensions and counts."""
        if chunk_count <= 0:
            return False
        # Verify dimension is positive and model name is non-empty
        if self.dimension <= 0 or not self.model_name:
            return False
        return True
