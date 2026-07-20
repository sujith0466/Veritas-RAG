"""Abstract base class interface for Cross-Encoder Reranker providers (`BaseRerankerProvider`).

Declares the standard contract for semantic re-scoring and re-ordering of merged candidate
chunks against the full query context (`ADR-002`).
"""

from abc import ABC, abstractmethod

from backend.modules.retrieval.schemas.retrieval_dto import RankedEvidenceDTO


class BaseRerankerProvider(ABC):
    """Abstract interface for cross-encoder reranking engines (`Cohere`, `Local Cross-Encoder`)."""

    @abstractmethod
    async def rerank(
        self, query: str, candidates: list[RankedEvidenceDTO], top_k: int = 10
    ) -> list[RankedEvidenceDTO]:
        """Re-evaluate and re-order candidate chunks against the search query.

        Args:
            query: Sanitized search query text.
            candidates: List of surviving unique candidates post-RRF fusion (`top N <= 30`).
            top_k: Number of top reranked evidence items to return.

        Returns:
            List of RankedEvidenceDTO with populated `rerank_score` and re-indexed `final_rank`.
        """
        ...
