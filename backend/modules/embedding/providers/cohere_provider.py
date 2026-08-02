"""Cohere Embedding Provider (`CohereEmbeddingProvider`).

Implements `BaseEmbeddingProvider` using async HTTP (`httpx`) against Cohere's REST API (`v1/embed`),
supporting enterprise multilingual search (`embed-multilingual-v3.0`) and input type separation (`search_document` vs `search_query`).
"""

from http import HTTPStatus

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

COHERE_EMBEDDING_API_URL = "https://api.cohere.ai/v1/embed"
COHERE_MODEL_DIMENSIONS: dict[str, int] = {
    "embed-multilingual-v3.0": 1024,
    "embed-english-v3.0": 1024,
    "embed-multilingual-light-v3.0": 384,
}


class CohereEmbeddingProvider(BaseEmbeddingProvider):
    """Async provider for Cohere multilingual and english embeddings."""

    def __init__(
        self,
        model_name: str | None = None,
        api_key: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        settings = get_settings().embeddings
        self._model = model_name or settings.cohere_model
        self._api_key = api_key or settings.cohere_api_key
        self._http_client = http_client

    @property
    def dimension(self) -> int:
        return COHERE_MODEL_DIMENSIONS.get(self._model, 1024)

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
                message=f"Cohere rate limit exceeded (HTTP 429): {response.text}",
                detail={"status_code": response.status_code, "body": response.text},
            )
        if response.status_code in {HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN}:
            raise ProviderAuthenticationError(
                message=f"Cohere authentication failed (HTTP {response.status_code})",
                detail={"status_code": response.status_code, "body": response.text},
            )
        if response.status_code == HTTPStatus.BAD_REQUEST:
            raise InvalidInputError(
                message=f"Cohere bad request (HTTP 400): {response.text}",
                detail={"status_code": response.status_code, "body": response.text},
            )
        if response.status_code >= HTTPStatus.INTERNAL_SERVER_ERROR:
            raise ProviderTimeoutError(
                message=f"Cohere upstream server error (HTTP {response.status_code})",
                detail={"status_code": response.status_code, "body": response.text},
            )
        if response.is_error:
            raise EmbeddingDomainException(
                code=EmbeddingErrorCode.EMB_004,
                message=f"Cohere API request failed: {response.status_code} - {response.text}",
                detail={"status_code": response.status_code, "body": response.text},
            )

    async def embed_documents(self, texts: list[str]) -> EmbeddingBatchResult:
        """Generate dense vector arrays for document chunks (`input_type='search_document'`)."""
        return await self._embed_batch(texts, input_type="search_document")

    async def embed_query(self, text: str) -> list[float]:
        """Generate a single vector for a query (`input_type='search_query'`)."""
        if not text or not text.strip():
            raise InvalidInputError(
                "Empty query string provided to CohereEmbeddingProvider."
            )
        res = await self._embed_batch([text], input_type="search_query")
        return res.embeddings[0]

    async def _embed_batch(
        self, texts: list[str], input_type: str
    ) -> EmbeddingBatchResult:
        if not texts:
            raise InvalidInputError(
                "Empty text batch provided to CohereEmbeddingProvider."
            )

        if not self._api_key:
            raise ProviderAuthenticationError("Missing Cohere API key configuration.")

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Request-Source": "python-sdk",
        }
        payload = {
            "texts": texts,
            "model": self._model,
            "input_type": input_type,
            "embedding_types": ["float"],
        }

        client = await self._get_client()
        should_close = self._http_client is None

        try:
            response = await client.post(
                COHERE_EMBEDDING_API_URL, headers=headers, json=payload
            )
            await self._handle_response_errors(response)
            data = response.json()

            embeddings_raw = data.get("embeddings", {})
            if isinstance(embeddings_raw, dict):
                vectors = embeddings_raw.get("float", [])
            else:
                vectors = embeddings_raw

            meta = data.get("meta", {})
            tokens = meta.get("billed_units", {}).get("input_tokens", 0)
            if tokens == 0:
                # Fallback estimation if not reported
                tokens = sum(len(t.split()) for t in texts)

            return EmbeddingBatchResult(
                embeddings=vectors,
                tokens_consumed=tokens,
                provider_metadata={"model": self._model, "meta": meta},
            )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            logger.warning("cohere_network_error", error=str(exc))
            raise ProviderTimeoutError(
                f"Cohere network timeout or connectivity issue: {exc}"
            ) from exc
        finally:
            if should_close:
                await client.aclose()
