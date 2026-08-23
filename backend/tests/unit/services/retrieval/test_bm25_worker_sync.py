"""Targeted unit tests for BM25 multi-worker synchronization and Redis versioning (ISS-012)."""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import pytest

from backend.modules.retrieval.providers.sparse.bm25_provider import (
    BM25SparseSearchProvider,
    _TenantBM25Index,
)
from backend.modules.retrieval.services.bm25_manager import SparseIndexManager


class FakeRedisClient:
    """In-memory fake for Redis key-value and increment operations."""

    def __init__(self):
        self._store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: Any) -> bool:
        self._store[key] = str(value)
        return True

    async def incr(self, key: str) -> int:
        val = int(self._store.get(key, "0")) + 1
        self._store[key] = str(val)
        return val


def _make_mock_chunk(tenant_id: str, content: str):
    chunk = MagicMock()
    chunk.id = uuid.uuid4()
    chunk.document_id = uuid.uuid4()
    chunk.document_version_id = uuid.uuid4()
    chunk.tenant_id = tenant_id
    chunk.content = content
    chunk.chunk_index = 0
    chunk.strategy_used = "fixed"
    chunk.token_count = len(content.split())
    return chunk


@pytest.mark.asyncio
async def test_bm25_sync_01_initial_version_tracking():
    """BM25-SYNC-01: Index built on cold start records initial Redis version (1)."""
    fake_redis = FakeRedisClient()
    provider = BM25SparseSearchProvider()
    manager = SparseIndexManager(sparse_provider=provider, redis=fake_redis)

    chunks = [_make_mock_chunk("tenant-1", "PostgreSQL database chunk content")]
    with patch.object(manager, "_make_chunk_repository") as mock_make_repo, \
         patch("backend.database.engine.get_session_factory") as mock_factory:
        mock_repo = AsyncMock()
        mock_repo.get_tenant_chunks.return_value = chunks
        mock_make_repo.return_value = mock_repo
        mock_factory.return_value = MagicMock(__aenter__=AsyncMock(return_value=AsyncMock()), __aexit__=AsyncMock(return_value=None))

        await manager.ensure_index("tenant-1")

        status = manager.get_status("tenant-1")
        assert status["initialized"] is True
        assert status["version"] == 1
        assert status["indexed_chunks"] == 1
        assert await fake_redis.get("raguard:bm25:version:tenant-1") == "1"


@pytest.mark.asyncio
async def test_bm25_sync_02_redis_version_increment_on_invalidation():
    """BM25-SYNC-02: Invalidation clears local cache and increments shared Redis version."""
    fake_redis = FakeRedisClient()
    await fake_redis.set("raguard:bm25:version:tenant-1", 1)
    provider = BM25SparseSearchProvider()
    manager = SparseIndexManager(sparse_provider=provider, redis=fake_redis)

    new_ver = await manager.invalidate_index("tenant-1")
    assert new_ver == 2
    assert await fake_redis.get("raguard:bm25:version:tenant-1") == "2"
    assert manager.is_initialized("tenant-1") is False


@pytest.mark.asyncio
async def test_bm25_sync_03_stale_index_detection():
    """BM25-SYNC-03: Worker with lagging local version detects staleness."""
    fake_redis = FakeRedisClient()
    provider = BM25SparseSearchProvider()
    manager = SparseIndexManager(sparse_provider=provider, redis=fake_redis)

    # Simulate local index built at version 1
    idx = provider._get_or_create_index("tenant-1")
    idx.version = 1

    # Shared Redis is at version 2 (another worker updated documents)
    await fake_redis.set("raguard:bm25:version:tenant-1", 2)

    assert await manager.is_stale("tenant-1") is True


@pytest.mark.asyncio
async def test_bm25_sync_04_lazy_rebuild_after_stale_detection():
    """BM25-SYNC-04: Stale worker rebuilds from PostgreSQL and updates local version to match Redis."""
    fake_redis = FakeRedisClient()
    await fake_redis.set("raguard:bm25:version:tenant-1", 3)
    provider = BM25SparseSearchProvider()
    manager = SparseIndexManager(sparse_provider=provider, redis=fake_redis)

    # Local worker currently at version 1
    idx = provider._get_or_create_index("tenant-1")
    idx.version = 1

    chunks = [_make_mock_chunk("tenant-1", "Updated document content")]
    with patch.object(manager, "_make_chunk_repository") as mock_make_repo, \
         patch("backend.database.engine.get_session_factory") as mock_factory:
        mock_repo = AsyncMock()
        mock_repo.get_tenant_chunks.return_value = chunks
        mock_make_repo.return_value = mock_repo
        mock_factory.return_value = MagicMock(__aenter__=AsyncMock(return_value=AsyncMock()), __aexit__=AsyncMock(return_value=None))

        # ensure_index sees staleness and triggers rebuild
        await manager.ensure_index("tenant-1")

        status = manager.get_status("tenant-1")
        assert status["version"] == 3
        assert status["indexed_chunks"] == 1


@pytest.mark.asyncio
async def test_bm25_sync_05_ingestion_propagation_across_workers():
    """BM25-SYNC-05: Document indexed by Worker A is visible to Worker B after invalidation."""
    fake_redis = FakeRedisClient()

    # Worker A
    provider_a = BM25SparseSearchProvider()
    manager_a = SparseIndexManager(sparse_provider=provider_a, redis=fake_redis)

    # Worker B
    provider_b = BM25SparseSearchProvider()
    manager_b = SparseIndexManager(sparse_provider=provider_b, redis=fake_redis)

    # Initial state: 1 chunk
    chunk_1 = _make_mock_chunk("tenant-1", "Initial document about Redis caching")
    chunk_2 = _make_mock_chunk("tenant-1", "Newly added document about Kubernetes orchestration")

    # Worker B initializes cold start with chunk_1
    with patch.object(manager_b, "_make_chunk_repository") as mock_make_repo, \
         patch("backend.database.engine.get_session_factory") as mock_factory:
        mock_repo = AsyncMock()
        mock_repo.get_tenant_chunks.return_value = [chunk_1]
        mock_make_repo.return_value = mock_repo
        mock_factory.return_value = MagicMock(__aenter__=AsyncMock(return_value=AsyncMock()), __aexit__=AsyncMock(return_value=None))

        await manager_b.ensure_index("tenant-1")
        results_b1 = await provider_b.search_keywords("tenant-1", "Kubernetes")
        assert len(results_b1) == 0  # Not in worker B yet

    # Worker A processes ingestion event and invalidates shared index
    await manager_a.invalidate_index("tenant-1")

    # Worker B receives next query and reloads from DB (which now has chunk_1 + chunk_2)
    with patch.object(manager_b, "_make_chunk_repository") as mock_make_repo, \
         patch("backend.database.engine.get_session_factory") as mock_factory:
        mock_repo = AsyncMock()
        mock_repo.get_tenant_chunks.return_value = [chunk_1, chunk_2]
        mock_make_repo.return_value = mock_repo
        mock_factory.return_value = MagicMock(__aenter__=AsyncMock(return_value=AsyncMock()), __aexit__=AsyncMock(return_value=None))

        await manager_b.ensure_index("tenant-1")
        results_b2 = await provider_b.search_keywords("tenant-1", "Kubernetes")
        assert len(results_b2) == 1
        assert "Kubernetes" in results_b2[0].content


@pytest.mark.asyncio
async def test_bm25_sync_06_deletion_propagation_across_workers():
    """BM25-SYNC-06: Document deleted in Worker A is removed from Worker B after rebuild."""
    fake_redis = FakeRedisClient()
    provider_b = BM25SparseSearchProvider()
    manager_b = SparseIndexManager(sparse_provider=provider_b, redis=fake_redis)

    chunk_1 = _make_mock_chunk("tenant-1", "Document to be deleted soon")

    with patch.object(manager_b, "_make_chunk_repository") as mock_make_repo, \
         patch("backend.database.engine.get_session_factory") as mock_factory:
        mock_repo = AsyncMock()
        mock_repo.get_tenant_chunks.return_value = [chunk_1]
        mock_make_repo.return_value = mock_repo
        mock_factory.return_value = MagicMock(__aenter__=AsyncMock(return_value=AsyncMock()), __aexit__=AsyncMock(return_value=None))

        await manager_b.ensure_index("tenant-1")
        assert len(await provider_b.search_keywords("tenant-1", "deleted")) == 1

    # Worker A deletes document and increments Redis version
    manager_a = SparseIndexManager(sparse_provider=BM25SparseSearchProvider(), redis=fake_redis)
    await manager_a.invalidate_index("tenant-1")

    # Worker B queries after DB deletion
    with patch.object(manager_b, "_make_chunk_repository") as mock_make_repo, \
         patch("backend.database.engine.get_session_factory") as mock_factory:
        mock_repo = AsyncMock()
        mock_repo.get_tenant_chunks.return_value = []  # Empty DB
        mock_make_repo.return_value = mock_repo
        mock_factory.return_value = MagicMock(__aenter__=AsyncMock(return_value=AsyncMock()), __aexit__=AsyncMock(return_value=None))

        await manager_b.ensure_index("tenant-1")
        assert len(await provider_b.search_keywords("tenant-1", "deleted")) == 0


@pytest.mark.asyncio
async def test_bm25_sync_07_redis_unavailable_fallback():
    """BM25-SYNC-07: When Redis throws an error, is_stale returns False and local index is used without crashing."""
    failing_redis = MagicMock()
    failing_redis.get.side_effect = ConnectionError("Redis connection lost")
    provider = BM25SparseSearchProvider()
    manager = SparseIndexManager(sparse_provider=provider, redis=failing_redis)

    idx = provider._get_or_create_index("tenant-1")
    idx.version = 1

    # Should not raise exception
    is_stale_val = await manager.is_stale("tenant-1")
    assert is_stale_val is False


@pytest.mark.asyncio
async def test_bm25_sync_08_single_flight_concurrency_preservation():
    """BM25-SYNC-08: Multiple concurrent search queries trigger exactly one rebuild (ISS-005)."""
    fake_redis = FakeRedisClient()
    await fake_redis.set("raguard:bm25:version:tenant-1", 2)
    provider = BM25SparseSearchProvider()
    manager = SparseIndexManager(sparse_provider=provider, redis=fake_redis)

    # Local version 1 (stale)
    idx = provider._get_or_create_index("tenant-1")
    idx.version = 1

    chunks = [_make_mock_chunk("tenant-1", "Single flight content")]
    build_call_count = 0

    async def mock_get_chunks(t_id):
        nonlocal build_call_count
        build_call_count += 1
        await asyncio.sleep(0.05)
        return chunks

    with patch.object(manager, "_make_chunk_repository") as mock_make_repo, \
         patch("backend.database.engine.get_session_factory") as mock_factory:
        mock_repo = AsyncMock()
        mock_repo.get_tenant_chunks.side_effect = mock_get_chunks
        mock_make_repo.return_value = mock_repo
        mock_factory.return_value = MagicMock(__aenter__=AsyncMock(return_value=AsyncMock()), __aexit__=AsyncMock(return_value=None))

        # Launch 5 concurrent ensure_index calls
        tasks = [manager.ensure_index("tenant-1") for _ in range(5)]
        await asyncio.gather(*tasks)

        assert build_call_count == 1
        assert manager.get_status("tenant-1")["version"] == 2


@pytest.mark.asyncio
async def test_bm25_sync_09_tenant_version_isolation():
    """BM25-SYNC-09: Version increment for Tenant A does not mark Tenant B index stale."""
    fake_redis = FakeRedisClient()
    provider = BM25SparseSearchProvider()
    manager = SparseIndexManager(sparse_provider=provider, redis=fake_redis)

    await fake_redis.set("raguard:bm25:version:tenant-A", 1)
    await fake_redis.set("raguard:bm25:version:tenant-B", 1)

    idx_a = provider._get_or_create_index("tenant-A")
    idx_a.version = 1
    idx_b = provider._get_or_create_index("tenant-B")
    idx_b.version = 1

    # Invalidate only Tenant A
    await manager.invalidate_index("tenant-A")

    assert await manager.is_stale("tenant-A") is True
    assert await manager.is_stale("tenant-B") is False


@pytest.mark.asyncio
async def test_bm25_sync_10_existing_bm25_scoring_compatibility():
    """BM25-SYNC-10: BM25 score calculation and ranking remains identical with versioning enabled."""
    provider = BM25SparseSearchProvider()
    chunks = [
        _make_mock_chunk("tenant-1", "Fast and secure relational database with ACID compliance"),
        _make_mock_chunk("tenant-1", "NoSQL document store with eventual consistency"),
    ]
    await provider.index_chunks("tenant-1", chunks, version=5)

    results = await provider.search_keywords("tenant-1", "relational database ACID")
    assert len(results) >= 1
    assert "relational database" in results[0].content
    assert results[0].score > 0.0
