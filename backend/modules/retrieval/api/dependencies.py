"""Retrieval API dependencies (`dependencies.py`).

Provides FastAPI dependency injection functions for repository access,
`RetrievalOrchestrator` instantiation with shared provider singletons, and
multi-tenant namespace resolution (`X-Tenant-ID`).
"""

from typing import Any

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.dependencies.auth import get_optional_user
from backend.core.dependencies.database import get_db
from backend.core.events.dispatcher import get_dispatcher
from backend.modules.embedding.providers.openai_provider import \
    OpenAIEmbeddingProvider
from backend.modules.retrieval.providers.reranker.local_reranker import \
    LocalCrossEncoderProvider
from backend.modules.retrieval.providers.sparse.bm25_provider import \
    BM25SparseSearchProvider
from backend.modules.retrieval.repositories.retrieval_repository import \
    RetrievalRepository
from backend.modules.retrieval.services.retrieval_service import \
    RetrievalOrchestrator
from backend.modules.vector.providers.qdrant_provider import \
    QdrantVectorDBProvider

# Global provider instances for connection reuse across HTTP requests
_qdrant_provider = QdrantVectorDBProvider()
_bm25_provider = BM25SparseSearchProvider()
_reranker_provider = LocalCrossEncoderProvider()


def resolve_tenant(
    user: Any | None = Depends(get_optional_user),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
) -> str:
    """Resolve active tenant identifier from user session or `X-Tenant-ID` header (`default_tenant` fallback)."""
    if user and getattr(user, "tenant_id", None):
        return str(user.tenant_id)
    return x_tenant_id or "default_tenant"


def get_retrieval_repository(
    session: AsyncSession = Depends(get_db),
) -> RetrievalRepository:
    """Inject a `RetrievalRepository` bound to the current request transaction session."""
    return RetrievalRepository(session)


def get_retrieval_orchestrator(
    session: AsyncSession = Depends(get_db),
    repository: RetrievalRepository = Depends(get_retrieval_repository),
) -> RetrievalOrchestrator:
    """Inject a `RetrievalOrchestrator` configured with shared vector, sparse, reranker providers, and event dispatcher."""
    embedding_provider = OpenAIEmbeddingProvider()
    return RetrievalOrchestrator(
        embedding_provider=embedding_provider,
        vector_provider=_qdrant_provider,
        sparse_provider=_bm25_provider,
        reranker_provider=_reranker_provider,
        repository=repository,
        event_dispatcher=get_dispatcher(),
    )
