"""Sparse Index Manager (`SparseIndexManager`).

Responsible for ensuring the BM25 index is initialized and synchronized
with the database chunks across multiple workers using Redis versioning.
Provides administrative and lifecycle hooks.

NOTE: This manager intentionally does NOT share the request-scoped
AsyncSession. It creates its own isolated sessions via get_session_factory()
to avoid asyncpg "another operation is in progress" errors during streaming.
"""
import asyncio
from typing import Any

from structlog import get_logger

from backend.cache.client import get_redis_client
from backend.modules.retrieval.providers.sparse.base import BaseSparseSearchProvider

logger = get_logger(__name__)


class SparseIndexManager:
    """Manages lifecycle, synchronization, and initialization of the BM25 sparse index."""

    def __init__(
        self,
        sparse_provider: BaseSparseSearchProvider | Any,
        redis: Any | None = None,
    ):
        self.sparse_provider = sparse_provider
        self.redis = redis if redis is not None else get_redis_client()
        self._tenant_locks: dict[str, asyncio.Lock] = {}
        self._lock_table_guard: asyncio.Lock | None = None

    def _get_guard(self) -> asyncio.Lock:
        if self._lock_table_guard is None:
            self._lock_table_guard = asyncio.Lock()
        return self._lock_table_guard

    async def _get_tenant_lock(self, tenant_id: str) -> asyncio.Lock:
        guard = self._get_guard()
        async with guard:
            if tenant_id not in self._tenant_locks:
                self._tenant_locks[tenant_id] = asyncio.Lock()
            return self._tenant_locks[tenant_id]

    def _make_chunk_repository(self, session):
        """Create a fresh chunk repository bound to the given isolated session."""
        from backend.modules.chunking.repositories.chunk_repository import DocumentChunkRepository
        return DocumentChunkRepository(session)

    def is_initialized(self, tenant_id: str) -> bool:
        """Check if the sparse index for the tenant is initialized in memory."""
        if hasattr(self.sparse_provider, "_indices"):
            return tenant_id in self.sparse_provider._indices
        return False

    async def is_stale(self, tenant_id: str) -> bool:
        """Check if the local in-memory index version lags behind the shared Redis version."""
        if not self.is_initialized(tenant_id):
            return True

        if self.redis:
            try:
                ver_str = await self.redis.get(f"raguard:bm25:version:{tenant_id}")
                if ver_str is not None:
                    current_ver = int(ver_str)
                    idx = self.sparse_provider._indices.get(tenant_id)
                    local_ver = getattr(idx, "version", 0) if idx else 0
                    if local_ver < current_ver:
                        return True
            except Exception as exc:
                # Option A: Availability-first fallback with degraded consistency telemetry
                logger.warning(
                    "Redis BM25 version check failed; operating with degraded consistency",
                    tenant_id=tenant_id,
                    error=str(exc),
                )
        return False

    async def ensure_index(self, tenant_id: str) -> None:
        """Ensure the tenant's index is built and up to date, loading from DB if necessary."""
        if self.is_initialized(tenant_id) and not await self.is_stale(tenant_id):
            return

        lock = await self._get_tenant_lock(tenant_id)
        async with lock:
            if self.is_initialized(tenant_id) and not await self.is_stale(tenant_id):
                return

            logger.info("BM25 index not initialized or stale for tenant. Building from database.", tenant_id=tenant_id)
            await self.rebuild_index(tenant_id)

    async def rebuild_index(self, tenant_id: str) -> int:
        """Clear and rebuild the tenant's BM25 index from all active chunks.

        Uses an INDEPENDENT session from get_session_factory() so the DB
        query never conflicts with the streaming request session.
        """
        from backend.database.engine import get_session_factory

        current_ver = 1
        if self.redis:
            try:
                ver_str = await self.redis.get(f"raguard:bm25:version:{tenant_id}")
                if ver_str is None:
                    await self.redis.set(f"raguard:bm25:version:{tenant_id}", 1)
                    current_ver = 1
                else:
                    current_ver = int(ver_str)
            except Exception as exc:
                logger.warning(
                    "Redis BM25 version read failed during rebuild; defaulting version",
                    tenant_id=tenant_id,
                    error=str(exc),
                )

        self.clear_index(tenant_id)

        session_factory = get_session_factory()
        async with session_factory() as session:
            chunk_repo = self._make_chunk_repository(session)
            chunks = await chunk_repo.get_tenant_chunks(tenant_id)

        if not chunks:
            logger.info("No chunks found to index for tenant.", tenant_id=tenant_id)
            await self.sparse_provider.index_chunks(tenant_id, [], version=current_ver)
            return 0

        indexed_count = await self.sparse_provider.index_chunks(
            tenant_id, list(chunks), version=current_ver
        )
        logger.info(
            "Rebuilt BM25 sparse index.",
            tenant_id=tenant_id,
            count=indexed_count,
            version=current_ver,
        )
        return indexed_count

    async def invalidate_index(self, tenant_id: str) -> int:
        """Clear local index and increment the shared Redis version counter for the tenant."""
        self.clear_index(tenant_id)
        new_ver = 1
        if self.redis:
            try:
                new_ver = await self.redis.incr(f"raguard:bm25:version:{tenant_id}")
            except Exception as exc:
                logger.warning(
                    "Redis BM25 version increment failed on invalidation",
                    tenant_id=tenant_id,
                    error=str(exc),
                )
        logger.info("Invalidated BM25 sparse index version for tenant", tenant_id=tenant_id, new_version=new_ver)
        return new_ver

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
        version = 0
        if initialized and hasattr(self.sparse_provider, "_indices"):
            idx = self.sparse_provider._indices.get(tenant_id)
            if idx:
                count = len(idx.documents)
                version = getattr(idx, "version", 0)

        return {
            "tenant_id": tenant_id,
            "initialized": initialized,
            "indexed_chunks": count,
            "version": version,
        }
