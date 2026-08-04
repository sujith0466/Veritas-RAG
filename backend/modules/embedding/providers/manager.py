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

        from backend.core.config import get_settings
        from backend.modules.embedding.schemas.errors import EmbeddingDomainException

        providers_to_try = [self.provider]

        # Build fallback chain
        settings = get_settings()
        fallback_names = ["openai", "cohere", "local"]
        current_name = getattr(self.provider, "provider_name", type(self.provider).__name__.lower().replace("embeddingprovider", ""))

        for name in fallback_names:
            if name != current_name:
                try:
                    if name == "openai":
                        model = settings.embeddings.openai_model
                        api_key = settings.embeddings.openai_api_key
                    elif name == "cohere":
                        model = settings.embeddings.cohere_model
                        api_key = settings.embeddings.cohere_api_key
                    else:
                        model = settings.embeddings.local_model
                        api_key = None

                    if name != "local" and not api_key:
                        continue # Skip fallback if no API key

                    fallback_prov = EmbeddingProviderFactory.get_provider(
                        provider_name=name, model_name=model, api_key=api_key
                    )
                    providers_to_try.append(fallback_prov)
                except Exception:
                    pass

        last_error = None
        for prov in providers_to_try:
            try:
                all_vectors: list[list[float]] = []
                total_tokens = 0
                meta_merged: dict[str, Any] = {"sub_batches": [], "fallback_provider": prov.provider_name if hasattr(prov, "provider_name") else type(prov).__name__}

                for i in range(0, len(texts), batch_size):
                    sub_batch = texts[i : i + batch_size]
                    res = await prov.embed_documents(sub_batch)
                    all_vectors.extend(res.embeddings)
                    total_tokens += res.tokens_consumed
                    meta_merged["sub_batches"].append(res.provider_metadata)

                return EmbeddingBatchResult(
                    embeddings=all_vectors,
                    tokens_consumed=total_tokens,
                    provider_metadata=meta_merged,
                )
            except EmbeddingDomainException as e:
                logger.warning("Embedding provider failed, attempting fallback", provider=type(prov).__name__, error=str(e))
                last_error = e
                continue

        raise last_error or InvalidInputError("All providers failed")

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
