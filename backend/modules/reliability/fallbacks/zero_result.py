"""Zero-Result Recoverer (`ADR-005`, `Phase 2 Milestone 5`).

Deterministic keyword broadening recovery engine that expands vocabulary
and strips English stopwords when initial queries surface 0 candidates.
"""

import time

import structlog

from backend.modules.reliability.schemas.errors import ZeroResultRecoveryFailedError
from backend.modules.reliability.schemas.reliability_dto import (
    ReliableCandidateDTO,
    ReliableRetrievalResultDTO,
)
from backend.modules.retrieval.providers.sparse.bm25_provider import (
    BM25SparseSearchProvider,
    tokenize,
)
from backend.modules.retrieval.schemas.errors import SparseIndexNotFoundError

logger = structlog.get_logger(__name__)


class ZeroResultRecoverer:
    """Recover from 0-result returns via fast keyword broadening without LLM overhead."""

    def __init__(self, sparse_provider: BM25SparseSearchProvider) -> None:
        self.sparse_provider = sparse_provider

    async def recover_empty_results(
        self,
        query: str,
        tenant_id: str,
        correlation_id: str,
        limit: int = 5,
    ) -> ReliableRetrievalResultDTO:
        """Strip stopwords, construct broadened term query, and execute secondary sparse lookup."""
        start_time = time.perf_counter()
        tokens = tokenize(query)

        if not tokens:
            logger.warning(
                "Zero-result query produced 0 tokens after stopword stripping",
                query=query,
            )
            raise ZeroResultRecoveryFailedError(
                tenant_id=tenant_id,
                query=query,
                detail={"reason": "No valid keywords left after stopword filtering"},
            )

        broadened_query = " ".join(tokens)
        logger.info(
            "Executing zero-result keyword broadening",
            tenant_id=tenant_id,
            original_query=query,
            broadened_query=broadened_query,
        )

        try:
            raw_candidates = await self.sparse_provider.search_keywords(
                tenant_id=tenant_id,
                query=broadened_query,
                limit=limit,
            )
        except SparseIndexNotFoundError as exc:
            logger.error(
                "Sparse index uninitialized during zero-result broadening",
                tenant_id=tenant_id,
            )
            raise ZeroResultRecoveryFailedError(
                tenant_id=tenant_id,
                query=query,
                detail={"reason": f"Sparse index uninitialized: {exc}"},
            ) from exc
        except Exception as exc:
            logger.error(
                "Unexpected error during zero-result recovery",
                tenant_id=tenant_id,
                exc_info=True,
            )
            raise ZeroResultRecoveryFailedError(
                tenant_id=tenant_id,
                query=query,
                detail={"reason": f"Execution failure: {exc}"},
            ) from exc

        if not raw_candidates:
            logger.info(
                "Zero-result recovery surfaced 0 candidates even after broadening",
                tenant_id=tenant_id,
            )
            raise ZeroResultRecoveryFailedError(
                tenant_id=tenant_id,
                query=query,
                detail={"reason": "No matches found for broadened tokens"},
            )

        candidates = [
            ReliableCandidateDTO(
                chunk_id=str(item.chunk_id),
                document_id=str(item.document_id),
                document_version_id=str(item.document_version_id),
                tenant_id=item.tenant_id,
                content=item.content,
                score=item.score,
                rank=idx + 1,
                source="zero_broadened",
                is_fallback=False,
                is_broadened=True,
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
            is_degraded_fallback=False,
            fallback_reason=None,
            is_zero_result_broadened=True,
        )
