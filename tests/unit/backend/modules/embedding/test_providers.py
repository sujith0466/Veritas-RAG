"""Unit tests for Phase 2 Milestone 2: Embedding Pipeline (Milestone C - Provider Layer).

Verifies `OpenAIEmbeddingProvider`, `CohereEmbeddingProvider`, `LocalEmbeddingProvider`,
and `EmbeddingManager` batch segmentation, factory resolution, and exact error taxonomy mapping.
"""

from http import HTTPStatus
from typing import Any

import httpx
import pytest

from backend.modules.embedding.providers.base import EmbeddingBatchResult
from backend.modules.embedding.providers.cohere_provider import CohereEmbeddingProvider
from backend.modules.embedding.providers.factory import EmbeddingProviderFactory
from backend.modules.embedding.providers.local_provider import LocalEmbeddingProvider
from backend.modules.embedding.providers.manager import EmbeddingManager
from backend.modules.embedding.providers.openai_provider import OpenAIEmbeddingProvider
from backend.modules.embedding.schemas.errors import (
    ProviderAuthenticationError,
    ProviderTimeoutError,
    RateLimitExceededError,
)


def create_mock_client(handler_fn: Any) -> httpx.AsyncClient:
    """Create an `httpx.AsyncClient` backed by `httpx.MockTransport`."""
    return httpx.AsyncClient(transport=httpx.MockTransport(handler_fn))


@pytest.mark.asyncio
class TestOpenAIEmbeddingProvider:
    """Test suite verifying OpenAI provider vector generation and HTTP error code mappings."""

    async def test_openai_success(self) -> None:
        def handler(req: httpx.Request) -> httpx.Response:
            assert req.url == "https://api.openai.com/v1/embeddings"
            body = json.loads(req.content)
            assert body["model"] == "text-embedding-3-large"
            assert len(body["input"]) == 2
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"index": 0, "embedding": [0.1] * 1536},
                        {"index": 1, "embedding": [0.2] * 1536},
                    ],
                    "usage": {"total_tokens": 14},
                },
            )

        import json
        client = create_mock_client(handler)
        provider = OpenAIEmbeddingProvider(model_name="text-embedding-3-large", api_key="test-key", http_client=client)

        assert provider.dimension == 1536
        res = await provider.embed_documents(["chunk one", "chunk two"])
        assert len(res.embeddings) == 2
        assert res.tokens_consumed == 14
        assert res.embeddings[0] == [0.1] * 1536

    async def test_openai_rate_limit_exceeded(self) -> None:
        def handler(req: httpx.Request) -> httpx.Response:
            return httpx.Response(HTTPStatus.TOO_MANY_REQUESTS, text="Rate limit exceeded")

        client = create_mock_client(handler)
        provider = OpenAIEmbeddingProvider(api_key="test-key", http_client=client)

        with pytest.raises(RateLimitExceededError) as exc:
            await provider.embed_documents(["hello"])
        assert exc.value.http_status == HTTPStatus.TOO_MANY_REQUESTS

    async def test_openai_auth_error(self) -> None:
        def handler(req: httpx.Request) -> httpx.Response:
            return httpx.Response(HTTPStatus.UNAUTHORIZED, text="Invalid API key")

        client = create_mock_client(handler)
        provider = OpenAIEmbeddingProvider(api_key="bad-key", http_client=client)

        with pytest.raises(ProviderAuthenticationError) as exc:
            await provider.embed_documents(["hello"])
        assert exc.value.http_status == HTTPStatus.UNAUTHORIZED

    async def test_openai_server_timeout_error(self) -> None:
        def handler(req: httpx.Request) -> httpx.Response:
            return httpx.Response(HTTPStatus.GATEWAY_TIMEOUT, text="Gateway Timeout")

        client = create_mock_client(handler)
        provider = OpenAIEmbeddingProvider(api_key="key", http_client=client)

        with pytest.raises(ProviderTimeoutError) as exc:
            await provider.embed_documents(["hello"])
        assert exc.value.http_status == HTTPStatus.GATEWAY_TIMEOUT

    async def test_openai_missing_api_key(self) -> None:
        provider = OpenAIEmbeddingProvider(api_key="")
        with pytest.raises(ProviderAuthenticationError):
            await provider.embed_documents(["test"])


@pytest.mark.asyncio
class TestCohereEmbeddingProvider:
    """Test suite verifying Cohere provider search document vs query handling and error mapping."""

    async def test_cohere_success(self) -> None:
        def handler(req: httpx.Request) -> httpx.Response:
            import json
            body = json.loads(req.content)
            assert body["model"] == "embed-multilingual-v3.0"
            assert body["input_type"] == "search_document"
            return httpx.Response(
                200,
                json={
                    "embeddings": {"float": [[0.5] * 1024]},
                    "meta": {"billed_units": {"input_tokens": 8}},
                },
            )

        client = create_mock_client(handler)
        provider = CohereEmbeddingProvider(model_name="embed-multilingual-v3.0", api_key="test-cohere", http_client=client)

        assert provider.dimension == 1024
        res = await provider.embed_documents(["test cohere"])
        assert len(res.embeddings) == 1
        assert len(res.embeddings[0]) == 1024
        assert res.tokens_consumed == 8

    async def test_cohere_embed_query(self) -> None:
        def handler(req: httpx.Request) -> httpx.Response:
            import json
            body = json.loads(req.content)
            assert body["input_type"] == "search_query"
            return httpx.Response(
                200,
                json={
                    "embeddings": [[0.3] * 1024],
                    "meta": {"billed_units": {"input_tokens": 3}},
                },
            )

        client = create_mock_client(handler)
        provider = CohereEmbeddingProvider(model_name="embed-multilingual-v3.0", api_key="key", http_client=client)
        vec = await provider.embed_query("what is self-correction?")
        assert len(vec) == 1024


@pytest.mark.asyncio
class TestLocalEmbeddingProvider:
    """Test suite verifying Local provider deterministic simulation and dimension consistency."""

    async def test_local_provider_deterministic_fallback(self) -> None:
        provider = LocalEmbeddingProvider(model_name="BAAI/bge-large-en-v1.5", offline=True)
        assert provider.dimension == 1024

        res = await provider.embed_documents(["local chunk 1", "local chunk 2"])
        assert len(res.embeddings) == 2
        assert len(res.embeddings[0]) == 1024
        assert res.tokens_consumed > 0

        # Verify deterministic consistency
        res2 = await provider.embed_documents(["local chunk 1"])
        assert res.embeddings[0] == res2.embeddings[0]

    async def test_local_provider_embed_query(self) -> None:
        provider = LocalEmbeddingProvider(model_name="BAAI/bge-small-en-v1.5", offline=True)
        assert provider.dimension == 384
        vec = await provider.embed_query("local search query")
        assert len(vec) == 384


@pytest.mark.asyncio
class TestEmbeddingManagerAndFactory:
    """Test suite verifying provider registration, factory resolution, and batch segmentation."""

    async def test_factory_resolves_registered_providers(self) -> None:
        openai_p = EmbeddingProviderFactory.get_provider("openai", api_key="k")
        assert isinstance(openai_p, OpenAIEmbeddingProvider)

        cohere_p = EmbeddingProviderFactory.get_provider("cohere", api_key="k")
        assert isinstance(cohere_p, CohereEmbeddingProvider)

        local_p = EmbeddingProviderFactory.get_provider("local")
        assert isinstance(local_p, LocalEmbeddingProvider)

    async def test_manager_sub_batching(self) -> None:
        class MockBatchProvider(LocalEmbeddingProvider):
            def __init__(self) -> None:
                super().__init__(model_name="BAAI/bge-small-en-v1.5", offline=True)
                self.calls = 0

            async def embed_documents(self, texts: list[str]) -> EmbeddingBatchResult:
                self.calls += 1
                return EmbeddingBatchResult(
                    embeddings=[[0.1] * 384 for _ in texts],
                    tokens_consumed=len(texts) * 5,
                )

        mock_provider = MockBatchProvider()
        manager = EmbeddingManager(provider_instance=mock_provider)

        # Vectorize 250 items with batch_size=100 -> exactly 3 calls (100, 100, 50)
        items = [f"item {i}" for i in range(250)]
        res = await manager.vectorize_batch(items, batch_size=100)

        assert mock_provider.calls == 3
        assert len(res.embeddings) == 250
        assert res.tokens_consumed == 250 * 5
        assert manager.validate_capabilities(chunk_count=250, max_tokens_per_chunk=512) is True
