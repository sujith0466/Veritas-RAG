"""Retrieval API dependencies (`dependencies.py`).

Provides FastAPI dependency injection functions for repository access,
`RetrievalOrchestrator` instantiation with shared provider singletons, and
multi-tenant namespace resolution.
"""

from typing import Any

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.dependencies.auth import get_optional_user
from backend.core.dependencies.database import get_db
from backend.core.events.dispatcher import get_dispatcher
from backend.modules.retrieval.providers.reranker.local_reranker import LocalCrossEncoderProvider
from backend.modules.retrieval.providers.sparse.bm25_provider import BM25SparseSearchProvider
from backend.modules.retrieval.repositories.retrieval_repository import RetrievalRepository
from backend.modules.retrieval.services.retrieval_service import RetrievalOrchestrator
from backend.modules.vector.providers.qdrant_provider import QdrantVectorDBProvider

# Global provider instances for connection reuse across HTTP requests
_qdrant_provider = QdrantVectorDBProvider()
_bm25_provider = BM25SparseSearchProvider()
# Reranker provider is instantiated lazily or per-request since it depends on settings



def resolve_tenant(
    user: Any | None = Depends(get_optional_user),
) -> str:
    """Resolve active workspace identifier from user session."""
    if not user or not getattr(user, "workspace_name", None) or user.workspace_name == "None":
        raise HTTPException(status_code=401, detail="Missing workspace context")
    return str(user.workspace_name)


def get_retrieval_repository(
    session: AsyncSession = Depends(get_db),
) -> RetrievalRepository:
    """Inject a `RetrievalRepository` bound to the current request transaction session."""
    return RetrievalRepository(session)


def get_sparse_index_manager() -> "SparseIndexManager":
    """Inject the SparseIndexManager for BM25 index operations.
    
    NOTE: Does NOT take a session dependency — SparseIndexManager creates
    its own isolated sessions internally to avoid streaming concurrency issues.
    """
    from backend.modules.retrieval.services.bm25_manager import SparseIndexManager
    return SparseIndexManager(sparse_provider=_bm25_provider)

_reranker_provider_instance = None

def get_retrieval_orchestrator(
    repository: RetrievalRepository = Depends(get_retrieval_repository),
    index_manager: "SparseIndexManager" = Depends(get_sparse_index_manager)
) -> RetrievalOrchestrator:
    """Inject a `RetrievalOrchestrator` configured with shared vector, sparse, reranker providers, and event dispatcher."""
    from backend.core.config import get_settings
    from backend.modules.embedding.providers.local_provider import LocalEmbeddingProvider

    global _reranker_provider_instance
    settings = get_settings()

    if _reranker_provider_instance is None:
        _reranker_provider_instance = LocalCrossEncoderProvider(model_name=settings.retrieval.reranker_model)

    embedding_provider = LocalEmbeddingProvider(model_name=settings.embeddings.local_model, offline=False)

    return RetrievalOrchestrator(
        embedding_provider=embedding_provider,
        vector_provider=_qdrant_provider,
        sparse_provider=_bm25_provider,
        reranker_provider=_reranker_provider_instance,
        repository=repository,
        event_dispatcher=get_dispatcher(),
        index_manager=index_manager
    )
