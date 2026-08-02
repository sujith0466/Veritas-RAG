"""Sparse Index Manager (`SparseIndexManager`).

Responsible for ensuring the BM25 index is initialized and synchronized
with the database chunks. Provides administrative and lifecycle hooks.

NOTE: This manager intentionally does NOT share the request-scoped
AsyncSession. It creates its own isolated sessions via get_session_factory()
to avoid asyncpg "another operation is in progress" errors during streaming.
"""
from typing import Any

from structlog import get_logger

from backend.modules.retrieval.providers.sparse.base import BaseSparseSearchProvider

logger = get_logger(__name__)


class SparseIndexManager:
    """Manages lifecycle and initialization of the BM25 sparse index."""

    def __init__(
        self,
        sparse_provider: BaseSparseSearchProvider | Any,
    ):
        self.sparse_provider = sparse_provider

    def _make_chunk_repository(self, session):
        """Create a fresh chunk repository bound to the given isolated session."""
        from backend.modules.chunking.repositories.chunk_repository import DocumentChunkRepository
        return DocumentChunkRepository(session)

    def is_initialized(self, tenant_id: str) -> bool:
        """Check if the sparse index for the tenant is initialized in memory."""
        if hasattr(self.sparse_provider, "_indices"):
            return tenant_id in self.sparse_provider._indices
        return False

    async def ensure_index(self, tenant_id: str) -> None:
        """Ensure the tenant's index is built, loading from DB if necessary."""
        if self.is_initialized(tenant_id):
            return

        logger.info("BM25 index not initialized for tenant. Building lazily.", tenant_id=tenant_id)
        await self.rebuild_index(tenant_id)

    async def rebuild_index(self, tenant_id: str) -> int:
        """Clear and rebuild the tenant's BM25 index from all active chunks.

        Uses an INDEPENDENT session from get_session_factory() so the DB
        query never conflicts with the streaming request session.
        """
        from backend.database.engine import get_session_factory
        self.clear_index(tenant_id)

        session_factory = get_session_factory()
        async with session_factory() as session:
            chunk_repo = self._make_chunk_repository(session)
            chunks = await chunk_repo.get_tenant_chunks(tenant_id)

        if not chunks:
            logger.info("No chunks found to index for tenant.", tenant_id=tenant_id)
            await self.sparse_provider.index_chunks(tenant_id, [])
            return 0

        indexed_count = await self.sparse_provider.index_chunks(tenant_id, list(chunks))
        logger.info("Rebuilt BM25 sparse index.", tenant_id=tenant_id, count=indexed_count)
        return indexed_count

    def clear_index(self, tenant_id: str) -> None:
        """Remove the tenant's index from memory."""
        if hasattr(self.sparse_provider, "_indices"):
            if tenant_id in self.sparse_provider._indices:
                del self.sparse_provider._indices[tenant_id]
                logger.debug("Cleared BM25 sparse index.", tenant_id=tenant_id)

    def get_status(self, tenant_id: str) -> dict[str, Any]:
        """Return the initialization status of the index."""
        initialized = self.is_initialized(tenant_id)
        count = 0
        if initialized and hasattr(self.sparse_provider, "_indices"):
            idx = self.sparse_provider._indices.get(tenant_id)
            if idx:
                count = len(idx.documents)

        return {
            "tenant_id": tenant_id,
            "initialized": initialized,
            "indexed_chunks": count
        }
