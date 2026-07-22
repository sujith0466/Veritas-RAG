"""Cohere Rerank API Provider (`CohereRerankerProvider`).

Wraps Cohere's async cross-encoder reranking endpoint (`rerank-english-v3.0`)
with automatic error mapping (`RET_003`) and top-k slicing (`ADR-002`).
"""

from typing import Any

from structlog import get_logger

from backend.modules.retrieval.providers.reranker.base import \
    BaseRerankerProvider
from backend.modules.retrieval.schemas.errors import RerankerTimeoutError
from backend.modules.retrieval.schemas.retrieval_dto import RankedEvidenceDTO

logger = get_logger(__name__)

try:
    import cohere
    from cohere.errors import CohereError

    COHERE_AVAILABLE = True
except ImportError:
    cohere = None
    CohereError = Exception
    COHERE_AVAILABLE = False


class CohereRerankerProvider(BaseRerankerProvider):
    """Cohere cross-encoder reranker wrapper (`rerank-english-v3.0`)."""

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = "rerank-english-v3.0",
        client: Any | None = None,
    ) -> None:
        self.model_name = model_name
        self._client = client
        if self._client is None and COHERE_AVAILABLE and api_key:
            self._client = cohere.AsyncClientV2(api_key=api_key)

    async def rerank(
        self, query: str, candidates: list[RankedEvidenceDTO], top_k: int = 10
    ) -> list[RankedEvidenceDTO]:
        """Execute Cohere rerank API on candidates."""
        if not candidates:
            return []

        # If <= 1 candidate, just re-index rank and return directly without making API call
        if len(candidates) <= 1:
            candidates[0].rerank_score = candidates[0].rrf_score
            candidates[0].final_rank = 1
            return candidates[:top_k]

        if self._client is None:
            raise RerankerTimeoutError(
                "Cohere client is not initialized or `cohere` SDK is unavailable (`RET_003`)."
            )

        documents = [c.content for c in candidates]
        try:
            response = await self._client.rerank(
                model=self.model_name,
                query=query,
                documents=documents,
                top_n=min(top_k, len(candidates)),
            )
        except Exception as exc:
            logger.error("Cohere rerank API execution failed", error=str(exc))
            raise RerankerTimeoutError(
                f"Cohere rerank request failed or timed out: {exc}"
            ) from exc

        reranked_results: list[RankedEvidenceDTO] = []
        # Response contains results ordered by relevance
        for idx, result in enumerate(response.results, start=1):
            original_candidate = candidates[result.index]
            original_candidate.rerank_score = round(float(result.relevance_score), 6)
            original_candidate.final_rank = idx
            reranked_results.append(original_candidate)

        logger.debug(
            "Completed Cohere reranking",
            model=self.model_name,
            input_count=len(candidates),
            output_count=len(reranked_results),
        )
        return reranked_results
