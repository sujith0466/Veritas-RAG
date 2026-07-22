"""Degraded Fallback Router (`ADR-005`, `Phase 2 Milestone 5`).

Routes queries to fast degraded fallback providers (e.g., BM25 sparse search)
when the primary hybrid retrieval engine circuit trips or times out.
"""

import time

import structlog

from backend.modules.reliability.schemas.errors import \
    FallbackProviderUnavailableError
from backend.modules.reliability.schemas.reliability_dto import (
    ReliableCandidateDTO, ReliableRetrievalResultDTO)
from backend.modules.retrieval.providers.sparse.bm25_provider import \
    BM25SparseSearchProvider
from backend.modules.retrieval.schemas.errors import SparseIndexNotFoundError

logger = structlog.get_logger(__name__)


class FallbackRouter:
    """Orchestrates fast degraded failover to sparse BM25 index when primary pipeline is OPEN."""

    def __init__(self, sparse_provider: BM25SparseSearchProvider) -> None:
        self.sparse_provider = sparse_provider

    async def route_fallback(
        self,
        query: str,
        tenant_id: str,
        reason: str,
        correlation_id: str,
        limit: int = 10,
    ) -> ReliableRetrievalResultDTO:
        """Route search to degraded BM25 sparse index and return flagged response."""
        start_time = time.perf_counter()
        logger.warning(
            "Routing query to degraded BM25 fallback path",
            tenant_id=tenant_id,
            reason=reason,
            correlation_id=correlation_id,
        )

        try:
            raw_candidates = await self.sparse_provider.search_keywords(
                tenant_id=tenant_id,
                query=query,
                limit=limit,
            )
        except SparseIndexNotFoundError as exc:
            logger.error(
                "Sparse fallback index not found for tenant",
                tenant_id=tenant_id,
                exc_info=True,
            )
            raise FallbackProviderUnavailableError(
                tenant_id=tenant_id,
                reason=f"Sparse BM25 index uninitialized (`RET_002`): {exc}",
            ) from exc
        except Exception as exc:
            logger.error(
                "Unexpected failure during degraded fallback execution",
                tenant_id=tenant_id,
                exc_info=True,
            )
            raise FallbackProviderUnavailableError(
                tenant_id=tenant_id, reason=f"Sparse BM25 execution failure: {exc}"
            ) from exc

        candidates = [
            ReliableCandidateDTO(
                chunk_id=str(item.chunk_id),
                document_id=str(item.document_id),
                document_version_id=str(item.document_version_id),
                tenant_id=item.tenant_id,
                content=item.content,
                score=item.score,
                rank=idx + 1,
                source="fallback_bm25",
                is_fallback=True,
                is_broadened=False,
                metadata=item.metadata,
            )
            for idx, item in enumerate(raw_candidates)
        ]

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return ReliableRetrievalResultDTO(
            query_text=query,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            candidates=candidates,
            duration_ms=duration_ms,
            is_sla_breached=False,
            is_degraded_fallback=True,
            fallback_reason=reason,
            is_zero_result_broadened=False,
        )
