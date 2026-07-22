"""Local HuggingFace/ONNX Embedding Provider (`LocalEmbeddingProvider`).

Implements `BaseEmbeddingProvider` for self-hosted, air-gapped dense vector generation (`sentence-transformers`),
with deterministic fallback pseudo-embedding calculation when local PyTorch weights are absent during offline/unit testing.
"""

import asyncio
import hashlib
import math
from typing import Any

import structlog

from backend.core.config import get_settings
from backend.modules.embedding.providers.base import (BaseEmbeddingProvider,
                                                      EmbeddingBatchResult)
from backend.modules.embedding.schemas.errors import InvalidInputError

logger = structlog.get_logger(__name__)

LOCAL_MODEL_DIMENSIONS: dict[str, int] = {
    "BAAI/bge-large-en-v1.5": 1024,
    "BAAI/bge-base-en-v1.5": 768,
    "BAAI/bge-small-en-v1.5": 384,
    "all-MiniLM-L6-v2": 384,
}


class LocalEmbeddingProvider(BaseEmbeddingProvider):
    """Self-hosted local dense embedding provider using `sentence-transformers` or deterministic simulation."""

    def __init__(
        self,
        model_name: str | None = None,
        api_key: str | None = None,
        offline: bool | None = None,
    ) -> None:
        settings = get_settings()
        self._model = model_name or settings.embeddings.local_model
        self._offline = offline if offline is not None else settings.app.is_testing
        self._st_model: Any | None = None
        self._st_attempted = False

    @property
    def dimension(self) -> int:
        return LOCAL_MODEL_DIMENSIONS.get(self._model, 1024)

    @property
    def model_name(self) -> str:
        return self._model

    def _get_or_load_model(self) -> Any | None:
        if self._offline:
            return None
        if self._st_model is not None:
            return self._st_model
        if self._st_attempted:
            return None

        self._st_attempted = True
        try:
            from sentence_transformers import SentenceTransformer

            self._st_model = SentenceTransformer(self._model)
            logger.info("local_sentence_transformer_loaded", model=self._model)
            return self._st_model
        except ImportError:
            logger.debug(
                "sentence_transformers_missing_using_deterministic_simulation",
                model=self._model,
            )
            return None
        except Exception as exc:
            logger.warning(
                "local_model_load_failed_using_deterministic_simulation", error=str(exc)
            )
            return None

    def _generate_deterministic_vector(self, text: str) -> list[float]:
        """Generate a deterministic unit-normalized pseudo-vector from text SHA-256 hash."""
        dim = self.dimension
        hash_bytes = hashlib.sha256(text.encode("utf-8")).digest()

        # Expand 32 hash bytes across `dim` dimensions deterministically
        raw_vec = []
        for i in range(dim):
            byte_val = hash_bytes[i % len(hash_bytes)]
            # Map byte (0..255) and index to float between -1.0 and 1.0
            val = ((byte_val - 128.0) / 128.0) * math.cos(i)
            raw_vec.append(val)

        # Unit normalize vector
        norm = math.sqrt(sum(v * v for v in raw_vec))
        if norm == 0.0:
            return [0.0] * dim
        return [round(v / norm, 6) for v in raw_vec]

    def _encode_sync(self, texts: list[str]) -> list[list[float]]:
        model = self._get_or_load_model()
        if model is not None:
            raw_vecs = model.encode(texts, normalize_embeddings=True)
            return [
                vec.tolist() if hasattr(vec, "tolist") else list(vec)
                for vec in raw_vecs
            ]
        return [self._generate_deterministic_vector(t) for t in texts]

    async def embed_documents(self, texts: list[str]) -> EmbeddingBatchResult:
        """Generate dense embedding vectors for input chunk texts."""
        if not texts:
            raise InvalidInputError(
                "Empty text batch provided to LocalEmbeddingProvider."
            )

        vectors = await asyncio.to_thread(self._encode_sync, texts)
        # Approximate token count for local model (words * 1.3)
        tokens = sum(int(len(t.split()) * 1.3) for t in texts)

        return EmbeddingBatchResult(
            embeddings=vectors,
            tokens_consumed=tokens,
            provider_metadata={
                "model": self._model,
                "local": self._st_model is not None,
            },
        )

    async def embed_query(self, text: str) -> list[float]:
        """Generate single vector embedding for a query string."""
        if not text or not text.strip():
            raise InvalidInputError(
                "Empty query string provided to LocalEmbeddingProvider."
            )
        res = await self.embed_documents([text])
        return res.embeddings[0]
