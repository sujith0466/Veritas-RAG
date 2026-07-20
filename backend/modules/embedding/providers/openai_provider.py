"""OpenAI Embedding Provider (`OpenAIEmbeddingProvider`).

Implements `BaseEmbeddingProvider` using async HTTP (`httpx`) against OpenAI's REST API (`v1/embeddings`),
providing native error classification (`EMB_001` through `EMB_005`) and token usage tracking.
"""

from http import HTTPStatus
from typing import Any
import httpx
import structlog

from backend.core.config import get_settings
from backend.modules.embedding.providers.base import BaseEmbeddingProvider, EmbeddingBatchResult
from backend.modules.embedding.schemas.errors import (
    EmbeddingDomainException,
    EmbeddingErrorCode,
    InvalidInputError,
    ProviderAuthenticationError,
    ProviderTimeoutError,
    RateLimitExceededError,
)

logger = structlog.get_logger(__name__)

OPENAI_EMBEDDING_API_URL = "https://api.openai.com/v1/embeddings"
MODEL_DIMENSIONS: dict[str, int] = {
    "text-embedding-3-large": 1536,
    "text-embedding-3-small": 1536,
    "text-embedding-ada-002": 1536,
}


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    """Async provider for OpenAI dense embeddings."""

    def __init__(
        self,
        model_name: str | None = None,
        api_key: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        settings = get_settings().embeddings
        self._model = model_name or settings.openai_model
        self._api_key = api_key or settings.openai_api_key
        self._http_client = http_client

    @property
    def dimension(self) -> int:
        return MODEL_DIMENSIONS.get(self._model, 1536)

    @property
    def model_name(self) -> str:
        return self._model

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is not None:
            return self._http_client
        return httpx.AsyncClient(timeout=30.0)

    async def _handle_response_errors(self, response: httpx.Response) -> None:
        if response.status_code == HTTPStatus.TOO_MANY_REQUESTS:
            raise RateLimitExceededError(
                message=f"OpenAI rate limit exceeded (HTTP 429): {response.text}",
                detail={"status_code": response.status_code, "body": response.text},
            )
        if response.status_code in {HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN}:
            raise ProviderAuthenticationError(
                message=f"OpenAI authentication failed (HTTP {response.status_code})",
                detail={"status_code": response.status_code, "body": response.text},
            )
        if response.status_code == HTTPStatus.BAD_REQUEST:
            raise InvalidInputError(
                message=f"OpenAI bad request (HTTP 400): {response.text}",
                detail={"status_code": response.status_code, "body": response.text},
            )
        if response.status_code >= HTTPStatus.INTERNAL_SERVER_ERROR:
            raise ProviderTimeoutError(
                message=f"OpenAI upstream server error (HTTP {response.status_code})",
                detail={"status_code": response.status_code, "body": response.text},
            )
        if response.is_error:
            raise EmbeddingDomainException(
                code=EmbeddingErrorCode.EMB_004,
                message=f"OpenAI API request failed: {response.status_code} - {response.text}",
                detail={"status_code": response.status_code, "body": response.text},
            )

    async def embed_documents(self, texts: list[str]) -> EmbeddingBatchResult:
        """Generate dense vector arrays for a batch of chunk texts."""
        if not texts:
            raise InvalidInputError("Empty text batch provided to OpenAIEmbeddingProvider.")

        if not self._api_key:
            raise ProviderAuthenticationError("Missing OpenAI API key configuration.")

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "input": texts,
            "model": self._model,
        }

        client = await self._get_client()
        should_close = self._http_client is None

        try:
            response = await client.post(OPENAI_EMBEDDING_API_URL, headers=headers, json=payload)
            await self._handle_response_errors(response)
            data = response.json()

            # Sort items by index to ensure order alignment with texts
            sorted_items = sorted(data.get("data", []), key=lambda x: x.get("index", 0))
            vectors = [item["embedding"] for item in sorted_items]
            tokens = data.get("usage", {}).get("total_tokens", 0)

            return EmbeddingBatchResult(
                embeddings=vectors,
                tokens_consumed=tokens,
                provider_metadata={"model": self._model, "usage": data.get("usage", {})},
            )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            logger.warning("openai_network_error", error=str(exc))
            raise ProviderTimeoutError(f"OpenAI network timeout or connectivity issue: {exc}") from exc
        finally:
            if should_close:
                await client.aclose()

    async def embed_query(self, text: str) -> list[float]:
        """Generate a single vector for a query string."""
        if not text or not text.strip():
            raise InvalidInputError("Empty query string provided to OpenAIEmbeddingProvider.")

        result = await self.embed_documents([text])
        return result.embeddings[0]
