"""Local Cross-Encoder Reranker Provider (`LocalCrossEncoderProvider`).

Wraps local cross-encoder model inference (`BAAI/bge-reranker-large`) using
sentence-transformers or ONNX runtime with top-n slicing (`ADR-002`).
"""

import asyncio
from typing import Any

from structlog import get_logger

from backend.modules.retrieval.providers.reranker.base import BaseRerankerProvider
from backend.modules.retrieval.schemas.errors import RerankerTimeoutError
from backend.modules.retrieval.schemas.retrieval_dto import RankedEvidenceDTO

logger = get_logger(__name__)

try:
    from sentence_transformers import CrossEncoder

    ST_AVAILABLE = True
except ImportError:
    CrossEncoder = None
    ST_AVAILABLE = False


class LocalCrossEncoderProvider(BaseRerankerProvider):
    """Local Cross-Encoder reranker wrapper (`BAAI/bge-reranker-large`)."""

    def __init__(
        self,
        model_name: str = "BAAI/bge-reranker-large",
        model: Any | None = None,
    ) -> None:
        self.model_name = model_name
        self._model = model
        import threading
        self._lock = threading.Lock()
        # Bounded concurrency: allows up to 4 concurrent model.predict() executions.
        # This prevents CPU thrashing/OOMs while dramatically improving P99 queuing latency
        # over a strict Lock(1) under heavy concurrent load.
        self._inference_lock = threading.Semaphore(4)

    def _get_model(self) -> Any:
        if self._model is not None:
            return self._model
        if not ST_AVAILABLE:
            raise RerankerTimeoutError(
                "Local cross-encoder (`sentence_transformers`) is not installed or model unavailable (`RET_003`)."
            )

        with self._lock:
            # Double-check locking
            if self._model is not None:
                return self._model

            try:
                self._model = CrossEncoder(self.model_name)
                return self._model
            except Exception as exc:
                raise RerankerTimeoutError(
                    f"Failed to load local cross-encoder model '{self.model_name}': {exc}"
                ) from exc

    def _predict_sync(self, query: str, texts: list[str]) -> list[float]:
        model = self._get_model()
        pairs = [(query, text) for text in texts]

        # Serialize inference to prevent CPU thrashing/contention under heavy concurrent load
        with self._inference_lock:
            scores = model.predict(pairs)

        return [float(s) for s in scores]

    async def rerank(
        self, query: str, candidates: list[RankedEvidenceDTO], top_k: int = 10
    ) -> list[RankedEvidenceDTO]:
        """Execute local cross-encoder scoring asynchronously."""
        if not candidates:
            return []

        if len(candidates) <= 1:
            candidates[0].raw_rerank_score = candidates[0].rrf_score
            candidates[0].final_rank = 1
            return candidates[:top_k]

        texts = [c.content for c in candidates]
        try:
            loop = asyncio.get_running_loop()
            scores = await loop.run_in_executor(None, self._predict_sync, query, texts)
        except Exception as exc:
            logger.error("Local cross-encoder inference failed", error=str(exc))
            if isinstance(exc, RerankerTimeoutError):
                raise
            raise RerankerTimeoutError(
                f"Local cross-encoder inference failed or timed out: {exc}"
            ) from exc

        scored_candidates: list[tuple[RankedEvidenceDTO, float]] = []
        for candidate, score in zip(candidates, scores, strict=True):
            candidate.raw_rerank_score = round(float(score), 6)
            scored_candidates.append((candidate, float(score)))

        # Sort descending by cross-encoder score
        scored_candidates.sort(key=lambda x: x[1], reverse=True)

        reranked_results: list[RankedEvidenceDTO] = []
        for idx, (candidate, _) in enumerate(scored_candidates[:top_k], start=1):
            candidate.final_rank = idx
            reranked_results.append(candidate)

        logger.debug(
            "Completed local cross-encoder reranking",
            model=self.model_name,
            input_count=len(candidates),
            output_count=len(reranked_results),
        )
        return reranked_results
