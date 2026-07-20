"""Celery Hybrid Retrieval Task (`execute_async_batch_search_task`).

Runs asynchronous batch hybrid search evaluations on the `retrieval` queue.
Enforces jittered exponential backoff retry policies for transient reranker timeouts (`RET_003`)
and vector store unavailability (`RET_004`) while failing fast on fatal syntax (`RET_001`)
or uninitialized index errors (`RET_002`).
"""

import asyncio
from typing import Any

from structlog import get_logger

from backend.database.engine import get_session_factory
from backend.modules.embedding.providers.cohere_provider import CohereEmbeddingProvider
from backend.modules.embedding.providers.openai_provider import OpenAIEmbeddingProvider
from backend.modules.retrieval.providers.reranker.local_reranker import (
    LocalCrossEncoderProvider,
)
from backend.modules.retrieval.providers.sparse.bm25_provider import (
    BM25SparseSearchProvider,
)
from backend.modules.retrieval.repositories.retrieval_repository import (
    RetrievalRepository,
)
from backend.modules.retrieval.schemas.errors import (
    ErrorSeverity,
    RetrievalDomainException,
)
from backend.modules.retrieval.schemas.retrieval_dto import SearchRequestDTO
from backend.modules.retrieval.services.retrieval_service import RetrievalOrchestrator
from backend.modules.vector.providers.qdrant_provider import QdrantVectorDBProvider
from backend.tasks.celery_app import celery_app

logger = get_logger(__name__)

# Shared provider singletons for async Celery task context
_qdrant_provider = QdrantVectorDBProvider()
_bm25_provider = BM25SparseSearchProvider()
_reranker_provider = LocalCrossEncoderProvider()


@celery_app.task(bind=True, queue="retrieval", max_retries=3, acks_late=True)
def execute_async_batch_search_task(
    self: Any,
    queries: list[str],
    tenant_id: str,
    top_k: int = 10,
    webhook_url: str | None = None,
) -> dict[str, Any]:
    """Background Celery task for executing batch hybrid search evaluations (`ADR-005`).

    Args:
        queries: List of query strings to search concurrently or sequentially.
        tenant_id: Tenant namespace ID.
        top_k: Number of final evidence chunks per query.
        webhook_url: Optional webhook URL to notify upon completion.

    Returns:
        Dictionary summary containing total processed queries and status.
    """
    try:
        return asyncio.run(
            _async_execute_batch_search(self, queries, tenant_id, top_k, webhook_url)
        )
    except RetrievalDomainException as exc:
        if exc.severity == ErrorSeverity.RECOVERABLE and self.request.retries < self.max_retries:
            countdown = int(2**self.request.retries * 3)
            logger.warning(
                "Recoverable retrieval error; scheduling exponential backoff retry",
                error_code=exc.code,
                attempt=self.request.retries + 1,
                countdown_s=countdown,
            )
            raise self.retry(exc=exc, countdown=countdown) from exc
        logger.error(
            "Fatal or max-retried retrieval error during batch search task",
            error_code=exc.code,
            error=str(exc),
        )
        raise


async def _async_execute_batch_search(
    task: Any,
    queries: list[str],
    tenant_id: str,
    top_k: int,
    webhook_url: str | None,
) -> dict[str, Any]:
    session_factory = get_session_factory()
    async with session_factory() as session:
        repository = RetrievalRepository(session)
        # Default embedding provider (OpenAI or Local fallback)
        embedding_provider = OpenAIEmbeddingProvider()

        orchestrator = RetrievalOrchestrator(
            embedding_provider=embedding_provider,
            vector_provider=_qdrant_provider,
            sparse_provider=_bm25_provider,
            reranker_provider=_reranker_provider,
            repository=repository,
        )

        results_summary: list[dict[str, Any]] = []
        for q in queries:
            req = SearchRequestDTO(query=q, top_k=top_k)
            res = await orchestrator.execute_hybrid_search(
                options=req, tenant_id=tenant_id
            )
            results_summary.append({
                "query": q,
                "correlation_id": res.correlation_id,
                "evidence_count": len(res.final_evidence),
                "duration_ms": res.stage_latencies.total_ms,
            })

        logger.info(
            "async_batch_search_completed",
            tenant_id=tenant_id,
            queries_count=len(queries),
            webhook=webhook_url,
        )
        return {
            "status": "COMPLETED",
            "tenant_id": tenant_id,
            "queries_processed": len(queries),
            "results": results_summary,
        }
