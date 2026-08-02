
retrieval_service = '''"""Hybrid Retrieval Orchestrator (`RetrievalOrchestrator`).

Coordinates multi-stage hybrid search (`ADR-005`), executing concurrent dense vector
and sparse keyword queries, rank fusion (`RRF`), deduplication (`ADR-M4-002`), 
cross-encoder reranking (`ADR-002`), and context compression with stage breakdown timers.
"""

import asyncio
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
    RankedEvidenceDTO,
    RetrievalQueryLogDTO,
    RetrievalResultDTOv2,
    RetrievalStageBreakdownDTO,
    SearchRequestDTO,
    SearchSandboxResponseDTO,
)
from backend.modules.retrieval.services.fusion import FusionEngine
from backend.modules.vector.providers.base import BaseVectorDBProvider

from backend.modules.retrieval.services.filter_dsl_compiler import FilterDSLCompiler
from backend.modules.retrieval.services.dedup_engine import DedupEngine
from backend.modules.retrieval.services.context_compressor import ContextCompressor
from backend.modules.retrieval.schemas.filter_dsl import CompressionOptionsDTO

logger = get_logger(__name__)


class RetrievalOrchestrator:
    """Master orchestrator for the Hybrid Retrieval Engine (`Phase 5`)."""

    def __init__(
        self,
        embedding_provider: BaseEmbeddingProvider | Any,
        vector_provider: BaseVectorDBProvider,
        sparse_provider: BaseSparseSearchProvider,
        reranker_provider: BaseRerankerProvider,
        filter_compiler: FilterDSLCompiler = None,
        repository: Any | None = None,
        event_dispatcher: Any | None = None,
        collection_prefix: str = "raguard_knowledge",
    ) -> None:
        self.embedding_provider = embedding_provider
        self.vector_provider = vector_provider
        self.sparse_provider = sparse_provider
        self.reranker_provider = reranker_provider
        self.filter_compiler = filter_compiler or FilterDSLCompiler()
        self.repository = repository
        self.event_dispatcher = event_dispatcher
        self.collection_prefix = collection_prefix

    def _get_collection_name(self) -> str:
        dimension = getattr(self.embedding_provider, "dimension", 1536)
        return f"{self.collection_prefix}_{dimension}"

    async def _execute_dense_stage(
        self,
        query: str,
        filter_conditions: dict[str, Any],
        collection_name: str,
        limit: int,
    ) -> tuple[list[CandidatePointDTO], float]:
        start_time = time.perf_counter()
        try:
            if hasattr(self.embedding_provider, "embed_query"):
                query_vector = await self.embedding_provider.embed_query(query)
            elif hasattr(self.embedding_provider, "vectorize_batch"):
                batch_res = await self.embedding_provider.vectorize_batch([query])
                query_vector = batch_res.embeddings[0]
            else:
                raise ValueError("Incompatible embedding provider passed to orchestrator.")

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
                    doc_uuid = UUID(str(raw_doc_id)) if raw_doc_id else UUID("00000000-0000-0000-0000-000000000000")
                except ValueError:
                    doc_uuid = UUID("00000000-0000-0000-0000-000000000000")

                raw_ver_id = payload.get("document_version_id")
                try:
                    ver_uuid = UUID(str(raw_ver_id)) if raw_ver_id else doc_uuid
                except ValueError:
                    ver_uuid = doc_uuid

                candidate = CandidatePointDTO(
                    chunk_id=chunk_uuid,
                    document_id=doc_uuid,
                    document_version_id=ver_uuid,
                    tenant_id=str(payload.get("tenant_id", filter_conditions.get("tenant_id"))),
                    content=str(payload.get("content", "")),
                    score=round(float(hit.get("score", 0.0)), 6),
                    source="dense",
                    rank=idx,
                    metadata=payload.get("metadata", {}),
                )
                candidates.append(candidate)

            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return candidates, duration_ms
        except Exception as exc:
            logger.error("Dense stage execution failed", error=str(exc))
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
            logger.warning(
                "Sparse index uninitialized for tenant during hybrid search",
                tenant_id=tenant_id,
                error=str(exc),
            )
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return [], duration_ms
        except Exception as exc:
            logger.error("Sparse stage execution failed", error=str(exc))
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return [], duration_ms

    def _validate_and_clean_query(self, query: str) -> str:
        clean = query.strip()
        if not clean or len(clean) > 2000:
            raise InvalidQueryError(
                "Search query must not be empty and must not exceed 2,000 characters (`RET_001`)."
            )
        return clean

    async def execute_hybrid_search(
        self,
        options: SearchRequestDTO,
        tenant_id: str,
        correlation_id: str = "auto",
    ) -> RetrievalResultDTOv2:
        """Execute complete multi-stage hybrid search v2."""
        total_start = time.perf_counter()
        query_clean = self._validate_and_clean_query(options.query)
        if correlation_id == "auto" or not correlation_id:
            correlation_id = f"req_{uuid4().hex[:8]}"
            
        # Compile Filter DSL
        filter_conditions = self.filter_compiler.compile(options.filter_dsl, tenant_id)

        try:
            collection_name = self._get_collection_name()

            # Stage 1: Parallel Dense + Sparse Retrieval
            dense_task = self._execute_dense_stage(
                query=query_clean,
                filter_conditions=filter_conditions,
                collection_name=collection_name,
                limit=options.limit_dense,
            )
            sparse_task = self._execute_sparse_stage(
                query=query_clean,
                tenant_id=tenant_id,
                limit=options.limit_sparse,
            )

            (dense_candidates, dense_ms), (sparse_candidates, sparse_ms) = (
                await asyncio.gather(dense_task, sparse_task)
            )

            # Stage 2: RRF Rank Fusion
            rrf_start = time.perf_counter()
            merged = FusionEngine.execute_rrf_fusion(
                dense_candidates, sparse_candidates, rrf_k=options.rrf_k
            )
            rrf_ms = (time.perf_counter() - rrf_start) * 1000.0

            # Stage 3: Deduplication
            dedup_start = time.perf_counter()
            dedup_engine = DedupEngine(jaccard_threshold=options.dedup_similarity_threshold)
            deduped, removed_count = dedup_engine.full_dedup_pipeline(merged)
            dedup_ms = (time.perf_counter() - dedup_start) * 1000.0

            # Stage 4: Cross-Encoder Reranking
            rerank_start = time.perf_counter()
            rerank_input = deduped[:30]
            try:
                final_evidence = await self.reranker_provider.rerank(
                    query=query_clean,
                    candidates=rerank_input,
                    top_k=options.top_k,
                )
            except Exception as e:
                logger.warning("Reranker failed, falling back to RRF ordering", error=str(e))
                final_evidence = rerank_input[:options.top_k]
            rerank_ms = (time.perf_counter() - rerank_start) * 1000.0
            
            # Stage 5: Context Compression
            comp_start = time.perf_counter()
            comp_options = options.compression_options or CompressionOptionsDTO(enabled=True)
            compressor = ContextCompressor(options=comp_options)
            final_evidence = compressor.compress_candidates(query_clean, final_evidence)
            comp_ms = (time.perf_counter() - comp_start) * 1000.0

            total_ms = (time.perf_counter() - total_start) * 1000.0
            stage_latencies = RetrievalStageBreakdownDTO(
                dense_ms=round(dense_ms, 2),
                sparse_ms=round(sparse_ms, 2),
                rrf_fusion_ms=round(rrf_ms, 2),
                dedup_ms=round(dedup_ms, 2),
                rerank_ms=round(rerank_ms, 2),
                compression_ms=round(comp_ms, 2),
                total_ms=round(total_ms, 2),
            )

            result = RetrievalResultDTOv2(
                query_text=query_clean,
                tenant_id=tenant_id,
                correlation_id=correlation_id,
                top_k_requested=options.top_k,
                dense_candidates_count=len(dense_candidates),
                sparse_candidates_count=len(sparse_candidates),
                unique_candidates_merged=len(deduped),
                final_evidence=final_evidence,
                stage_latencies=stage_latencies,
                dedup_removed_count=removed_count,
                filter_applied=options.filter_dsl is not None,
            )
            return result
        finally:
            pass

'''
with open("backend/modules/retrieval/services/retrieval_service.py", "w") as f:
    f.write(retrieval_service)
print("Updated retrieval_service.py")
