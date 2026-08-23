"""Hybrid Retrieval Orchestrator (`RetrievalOrchestrator`).

Coordinates multi-stage hybrid search (`ADR-005`), executing concurrent dense vector
and sparse keyword queries (`await asyncio.gather()`), rank fusion (`RRF`), near-duplicate
deduplication (`ADR-M4-002`), and cross-encoder reranking (`ADR-002`) with stage breakdown timers.
"""

import asyncio
import math
import time
from typing import Any
from uuid import UUID, uuid4

from structlog import get_logger

from backend.modules.embedding.providers.base import BaseEmbeddingProvider
from backend.modules.retrieval.providers.reranker.base import BaseRerankerProvider
from backend.modules.retrieval.providers.sparse.base import BaseSparseSearchProvider
from backend.modules.retrieval.schemas.errors import (
    InvalidQueryError,
    SparseIndexNotFoundError,
    VectorStoreUnavailableError,
)
from backend.modules.retrieval.schemas.retrieval_dto import (
    CandidatePointDTO,
    RetrievalQueryLogDTO,
    RetrievalResultDTO,
    RetrievalStageBreakdownDTO,
    SearchRequestDTO,
    SearchSandboxResponseDTO,
)
from backend.modules.retrieval.services.fusion import FusionEngine
from backend.modules.vector.providers.base import BaseVectorDBProvider

logger = get_logger(__name__)


class RetrievalOrchestrator:
    """Master orchestrator for the Hybrid Retrieval Engine (`Milestone 4`)."""

    def __init__(
        self,
        embedding_provider: BaseEmbeddingProvider | Any,
        vector_provider: BaseVectorDBProvider,
        sparse_provider: BaseSparseSearchProvider,
        reranker_provider: BaseRerankerProvider,
        repository: Any | None = None,
        event_dispatcher: Any | None = None,
        index_manager: Any | None = None,
    ) -> None:
        self.embedding_provider = embedding_provider
        self.vector_provider = vector_provider
        self.sparse_provider = sparse_provider
        self.reranker_provider = reranker_provider
        self.repository = repository
        self.event_dispatcher = event_dispatcher
        self.index_manager = index_manager

    def _get_collection_name(self, options: SearchRequestDTO, tenant_id: str = None) -> str:
        if (
            hasattr(options, "filter_dsl")
            and options.filter_dsl
            and getattr(options.filter_dsl, "collection_name", None)
        ):
            return str(options.filter_dsl.collection_name)
        if (
            hasattr(options, "filters")
            and getattr(options, "filters", None)
            and isinstance(options.filters, dict)
            and options.filters.get("collection_name")
        ):
            return str(options.filters["collection_name"])

        # FIX: Ensure we use the exact same tenant-scoped naming convention
        # as the ingestion pipeline (VectorStorageService).
        from backend.core.config import get_settings
        if tenant_id:
            return get_settings().qdrant.collection_name(tenant_id)
        return get_settings().qdrant.collection_prefix

    async def _execute_dense_stage(
        self,
        query: str,
        tenant_id: str,
        collection_name: str,
        limit: int,
        filters: dict[str, Any] | None,
    ) -> tuple[list[CandidatePointDTO], float]:
        start_time = time.perf_counter()
        try:
            if hasattr(self.embedding_provider, "embed_query"):
                query_vector = await self.embedding_provider.embed_query(query)
            elif hasattr(self.embedding_provider, "vectorize_batch"):
                batch_res = await self.embedding_provider.vectorize_batch([query])
                query_vector = batch_res.embeddings[0]
            else:
                raise ValueError(
                    "Incompatible embedding provider passed to orchestrator."
                )

            filter_conditions = {"tenant_id": tenant_id}
            if filters:
                for k, v in filters.items():
                    if k != "collection_name":
                        filter_conditions[k] = v

            raw_hits = await self.vector_provider.search_points(
                collection_name=collection_name,
                query_vector=query_vector,
                filter_conditions=filter_conditions,
                limit=limit,
            )

            candidates: list[CandidatePointDTO] = []
            for idx, hit in enumerate(raw_hits, start=1):
                payload = hit.get("payload", {})
                raw_cid = payload.get("chunk_id") or hit.get("point_id")
                try:
                    chunk_uuid = UUID(str(raw_cid)) if raw_cid else uuid4()
                except ValueError:
                    chunk_uuid = uuid4()

                raw_doc_id = payload.get("document_id")
                try:
                    doc_uuid = (
                        UUID(str(raw_doc_id))
                        if raw_doc_id
                        else UUID("00000000-0000-0000-0000-000000000000")
                    )
                except ValueError:
                    doc_uuid = UUID("00000000-0000-0000-0000-000000000000")

                raw_ver_id = payload.get("document_version_id")
                try:
                    ver_uuid = UUID(str(raw_ver_id)) if raw_ver_id else doc_uuid
                except ValueError:
                    ver_uuid = doc_uuid

                metadata_keys = set(payload.keys()) - {"tenant_id", "content", "chunk_id", "document_id", "document_version_id", "score"}
                metadata_dict = {k: payload[k] for k in metadata_keys}

                candidate = CandidatePointDTO(
                    chunk_id=chunk_uuid,
                    document_id=doc_uuid,
                    document_version_id=ver_uuid,
                    tenant_id=str(payload.get("tenant_id", tenant_id)),
                    content=str(payload.get("content", "")),
                    score=round(float(hit.get("score", 0.0)), 6),
                    source="dense",
                    rank=idx,
                    metadata=metadata_dict,
                )
                candidates.append(candidate)

            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return candidates, duration_ms
        except Exception as exc:
            err_str = str(exc)
            if "Not found: Collection" in err_str or (hasattr(exc, "status_code") and exc.status_code == 404):
                logger.info("Collection missing for workspace, treating as empty knowledge base.", collection_name=collection_name)
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                return [], duration_ms

            logger.error("Dense stage execution failed", error=err_str)
            raise VectorStoreUnavailableError(
                f"Dense vector retrieval failed (`RET_004`): {exc}"
            ) from exc

    async def _execute_sparse_stage(
        self, query: str, tenant_id: str, limit: int
    ) -> tuple[list[CandidatePointDTO], float]:
        start_time = time.perf_counter()
        try:
            candidates = await self.sparse_provider.search_keywords(
                tenant_id=tenant_id,
                query=query,
                limit=limit,
            )
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return candidates, duration_ms
        except SparseIndexNotFoundError as exc:
            if self.index_manager:
                try:
                    logger.info(
                        "Sparse index uninitialized for tenant; triggering lazy auto-recovery",
                        tenant_id=tenant_id,
                    )
                    await self.index_manager.ensure_index(tenant_id)
                    candidates = await self.sparse_provider.search_keywords(
                        tenant_id=tenant_id,
                        query=query,
                        limit=limit,
                    )
                    duration_ms = (time.perf_counter() - start_time) * 1000.0
                    return candidates, duration_ms
                except Exception as auto_exc:
                    logger.error(
                        "BM25 lazy index recovery failed; returning empty sparse set",
                        tenant_id=tenant_id,
                        error=str(auto_exc),
                    )
            else:
                logger.warning(
                    "Sparse index uninitialized and no index manager available; returning empty sparse set",
                    tenant_id=tenant_id,
                    error=str(exc),
                )
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return [], duration_ms
        except Exception as exc:
            logger.error("Sparse stage execution failed", error=str(exc))
            # If unexpected error in sparse, return empty list to allow fallback/degradation
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return [], duration_ms

    def _validate_and_clean_query(self, query: str) -> str:
        clean = query.strip()
        if not clean or len(clean) > 2000:
            raise InvalidQueryError(
                "Search query must not be empty and must not exceed 2,000 characters (`RET_001`)."
            )
        return clean

    async def _log_and_emit(
        self,
        tenant_id: str,
        correlation_id: str,
        query_text: str,
        dense_count: int,
        sparse_count: int,
        merged_count: int,
        final_top_k: int,
        stage_latencies: RetrievalStageBreakdownDTO,
    ) -> None:
        if self.repository:
            try:
                log_dto = RetrievalQueryLogDTO(
                    id=uuid4(),
                    tenant_id=tenant_id,
                    correlation_id=correlation_id,
                    query_text=query_text,
                    dense_candidate_count=dense_count,
                    sparse_candidate_count=sparse_count,
                    merged_unique_count=merged_count,
                    final_top_k=final_top_k,
                    total_duration_ms=stage_latencies.total_ms,
                    stage_breakdown_json=stage_latencies.model_dump(),
                )
                await self.repository.log_query_execution(log_dto)
            except Exception as exc:
                logger.error(
                    "Failed to asynchronously log query execution history",
                    error=str(exc),
                )

        if self.event_dispatcher:
            try:
                from backend.modules.retrieval.events.payloads import (
                    QueryRetrievedPayload,
                    RetrievalDomainEvent,
                )

                payload = QueryRetrievedPayload(
                    event_id=str(uuid4()),
                    tenant_id=tenant_id,
                    correlation_id=correlation_id,
                    query_text=query_text,
                    top_k_requested=final_top_k,
                    dense_candidates_found=dense_count,
                    sparse_candidates_found=sparse_count,
                    unique_merged_candidates=merged_count,
                    reranker_model=getattr(
                        self.reranker_provider, "model_name", "unknown"
                    ),
                    duration_ms=stage_latencies.total_ms,
                    stage_latencies=stage_latencies.model_dump(),
                )
                from backend.core.events.types import EventType

                await self.event_dispatcher.publish(
                    RetrievalDomainEvent(
                        event_type=EventType.QUERY_RETRIEVED, payload=payload
                    )
                )
            except Exception as exc:
                logger.error(
                    "Failed to emit QueryRetrieved domain event", error=str(exc)
                )

    async def execute_hybrid_search(
        self,
        options: SearchRequestDTO,
        tenant_id: str,
        correlation_id: str = "auto",
    ) -> RetrievalResultDTO:
        """Execute complete multi-stage hybrid search (`Dense + Sparse -> RRF -> Deduplicate -> Rerank`)."""
        total_start = time.perf_counter()
        query_clean = self._validate_and_clean_query(options.query)
        if correlation_id == "auto" or not correlation_id:
            correlation_id = f"req_{uuid4().hex[:8]}"

        from backend.observability.metrics import record_stage_duration
        from backend.observability.tracing import trace_retrieval

        span_ctx = trace_retrieval("hybrid_rrf", options.top_k, tenant_id=tenant_id)
        span_ctx.__enter__()
        try:
            collection_name = self._get_collection_name(options, tenant_id=tenant_id)

            # Stage 1: Parallel Dense + Sparse Retrieval (`await asyncio.gather`)
            dense_task = self._execute_dense_stage(
                query=query_clean,
                tenant_id=tenant_id,
                collection_name=collection_name,
                limit=options.limit_dense,
                filters=getattr(options, "filter_dsl", None)
                or getattr(options, "filters", None),
            )
            sparse_task = self._execute_sparse_stage(
                query=query_clean,
                tenant_id=tenant_id,
                limit=options.limit_sparse,
            )

            (dense_candidates, dense_ms), (sparse_candidates, sparse_ms) = (
                await asyncio.gather(dense_task, sparse_task)
            )

            # Stage 2: RRF Rank Fusion & Near-Duplicate Deduplication (`FusionEngine`)
            rrf_start = time.perf_counter()
            merged = FusionEngine.execute_rrf_fusion(
                dense_candidates, sparse_candidates, rrf_k=options.rrf_k
            )
            deduped = FusionEngine.deduplicate_candidates(
                merged, similarity_threshold=options.dedup_similarity_threshold
            )
            rrf_ms = (time.perf_counter() - rrf_start) * 1000.0

            # Stage 3: Cross-Encoder Reranking (`strictly bounded to top N <= 30 per ADR-M4-002`)
            rerank_start = time.perf_counter()
            rerank_input = deduped[:30]
            final_evidence = await self.reranker_provider.rerank(
                query=query_clean,
                candidates=rerank_input,
                top_k=options.top_k,
            )

            # Centralized Provider-Independent Score Normalization Layer
            for candidate in final_evidence:
                score = candidate.raw_rerank_score
                if score is not None:
                    # Apply sigmoid to convert cross-encoder logits ([-10, 10]) into probabilities ([0, 1])
                    candidate.normalized_relevance_score = round(1.0 / (1.0 + math.exp(-score)), 6)
                else:
                    # Fallback to RRF score if reranking was bypassed
                    candidate.normalized_relevance_score = candidate.rrf_score

            rerank_ms = (time.perf_counter() - rerank_start) * 1000.0

            total_ms = (time.perf_counter() - total_start) * 1000.0
            stage_latencies = RetrievalStageBreakdownDTO(
                dense_ms=round(dense_ms, 2),
                sparse_ms=round(sparse_ms, 2),
                rrf_fusion_ms=round(rrf_ms, 2),
                rerank_ms=round(rerank_ms, 2),
                total_ms=round(total_ms, 2),
            )

            # Keep audit logging inside the request-scoped DB session lifetime.
            await self._log_and_emit(
                tenant_id=tenant_id,
                correlation_id=correlation_id,
                query_text=query_clean,
                dense_count=len(dense_candidates),
                sparse_count=len(sparse_candidates),
                merged_count=len(deduped),
                final_top_k=len(final_evidence),
                stage_latencies=stage_latencies,
            )

            result = RetrievalResultDTO(
                query_text=query_clean,
                tenant_id=tenant_id,
                correlation_id=correlation_id,
                top_k_requested=options.top_k,
                dense_candidates_count=len(dense_candidates),
                sparse_candidates_count=len(sparse_candidates),
                unique_candidates_merged=len(deduped),
                final_evidence=final_evidence,
                stage_latencies=stage_latencies,
            )
            return result
        finally:
            duration_sec = time.perf_counter() - total_start
            record_stage_duration("retrieval", duration_sec)
            import sys

            span_ctx.__exit__(*sys.exc_info())

    async def execute_sandbox_search(
        self,
        options: SearchRequestDTO,
        tenant_id: str,
        correlation_id: str = "auto",
    ) -> SearchSandboxResponseDTO:
        """Execute side-by-side comparative multi-stage search for Sandbox UI (`ADR-005`)."""
        total_start = time.perf_counter()
        query_clean = self._validate_and_clean_query(options.query)
        if correlation_id == "auto" or not correlation_id:
            correlation_id = f"req_{uuid4().hex[:8]}"

        collection_name = self._get_collection_name(options)

        dense_task = self._execute_dense_stage(
            query=query_clean,
            tenant_id=tenant_id,
            collection_name=collection_name,
            limit=options.limit_dense,
            filters=getattr(options, "filter_dsl", None)
            or getattr(options, "filters", None),
        )
        sparse_task = self._execute_sparse_stage(
            query=query_clean,
            tenant_id=tenant_id,
            limit=options.limit_sparse,
        )

        (dense_candidates, dense_ms), (sparse_candidates, sparse_ms) = (
            await asyncio.gather(dense_task, sparse_task)
        )

        rrf_start = time.perf_counter()
        merged = FusionEngine.execute_rrf_fusion(
            dense_candidates, sparse_candidates, rrf_k=options.rrf_k
        )
        deduped = FusionEngine.deduplicate_candidates(
            merged, similarity_threshold=options.dedup_similarity_threshold
        )
        rrf_ms = (time.perf_counter() - rrf_start) * 1000.0

        rerank_start = time.perf_counter()
        rerank_input = [c.model_copy(deep=True) for c in deduped[:30]]
        final_reranked = await self.reranker_provider.rerank(
            query=query_clean,
            candidates=rerank_input,
            top_k=options.top_k,
        )

        # Centralized Provider-Independent Score Normalization Layer
        for candidate in final_reranked:
            score = candidate.raw_rerank_score
            if score is not None:
                candidate.normalized_relevance_score = round(1.0 / (1.0 + math.exp(-score)), 6)
            else:
                candidate.normalized_relevance_score = candidate.rrf_score

        rerank_ms = (time.perf_counter() - rerank_start) * 1000.0

        total_ms = (time.perf_counter() - total_start) * 1000.0
        stage_latencies = RetrievalStageBreakdownDTO(
            dense_ms=round(dense_ms, 2),
            sparse_ms=round(sparse_ms, 2),
            rrf_fusion_ms=round(rrf_ms, 2),
            rerank_ms=round(rerank_ms, 2),
            total_ms=round(total_ms, 2),
        )

        await self._log_and_emit(
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            query_text=query_clean,
            dense_count=len(dense_candidates),
            sparse_count=len(sparse_candidates),
            merged_count=len(deduped),
            final_top_k=len(final_reranked),
            stage_latencies=stage_latencies,
        )

        response = SearchSandboxResponseDTO(
            query_text=query_clean,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            dense_results=dense_candidates[: options.top_k],
            sparse_results=sparse_candidates[: options.top_k],
            rrf_merged_results=deduped[: options.top_k],
            final_reranked_results=final_reranked,
            stage_latencies=stage_latencies,
        )
        return response
