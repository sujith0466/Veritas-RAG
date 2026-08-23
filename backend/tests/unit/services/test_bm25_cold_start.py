"""Unit tests for BM25 Cold-Start Auto-Recovery & Lifecycle Management (ISS-005)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock
import uuid
import pytest

from backend.modules.retrieval.providers.sparse.bm25_provider import BM25SparseSearchProvider
from backend.modules.retrieval.services.bm25_manager import SparseIndexManager
from backend.modules.retrieval.services.retrieval_service import RetrievalOrchestrator
from backend.modules.retrieval.schemas.retrieval_dto import SearchRequestDTO


def _create_mock_chunk(tenant_id: str, content: str, doc_id: str | None = None) -> MagicMock:
    chunk = MagicMock()
    chunk.id = uuid.uuid4()
    chunk.tenant_id = tenant_id
    chunk.document_id = uuid.UUID(doc_id) if doc_id else uuid.uuid4()
    chunk.document_version_id = uuid.uuid4()
    chunk.chunk_index = 0
    chunk.content = content
    chunk.strategy_used = "recursive"
    chunk.token_count = len(content.split())
    return chunk


@pytest.mark.asyncio
async def test_bm25_cold_start_auto_recovery():
    """Test 1: Fresh uninitialized tenant query triggers ensure_index() and returns sparse candidates."""
    provider = BM25SparseSearchProvider()
    manager = SparseIndexManager(sparse_provider=provider)

    tenant_id = "tenant_cold_start_1"
    chunk1 = _create_mock_chunk(tenant_id, "Enterprise risk management and TLS authentication.")

    mock_repo = MagicMock()
    mock_repo.get_tenant_chunks = AsyncMock(return_value=[chunk1])
    manager._make_chunk_repository = MagicMock(return_value=mock_repo)

    mock_embedding = MagicMock()
    mock_embedding.embed_query = AsyncMock(return_value=[0.1] * 384)

    mock_vector = MagicMock()
    mock_vector.search_points = AsyncMock(return_value=[])

    mock_reranker = MagicMock()
    mock_reranker.rerank = AsyncMock(side_effect=lambda query, candidates, top_k: candidates[:top_k])

    orchestrator = RetrievalOrchestrator(
        embedding_provider=mock_embedding,
        vector_provider=mock_vector,
        sparse_provider=provider,
        reranker_provider=mock_reranker,
        index_manager=manager,
    )

    assert not manager.is_initialized(tenant_id)

    search_req = SearchRequestDTO(query="risk management TLS", top_k=5)
    result = await orchestrator.execute_hybrid_search(
        options=search_req,
        tenant_id=tenant_id,
        correlation_id="corr_test_1",
    )

    assert manager.is_initialized(tenant_id)
    assert result.sparse_candidates_count == 1
    assert len(result.final_evidence) == 1
    assert "Enterprise risk management" in result.final_evidence[0].content


@pytest.mark.asyncio
async def test_subsequent_query_does_not_rebuild():
    """Test 2: Subsequent queries reuse the in-memory index without invoking rebuild."""
    provider = BM25SparseSearchProvider()
    manager = SparseIndexManager(sparse_provider=provider)

    tenant_id = "tenant_reuse_1"
    chunk1 = _create_mock_chunk(tenant_id, "Zero trust network architecture and IAM.")

    mock_repo = MagicMock()
    mock_repo.get_tenant_chunks = AsyncMock(return_value=[chunk1])
    manager._make_chunk_repository = MagicMock(return_value=mock_repo)

    await manager.ensure_index(tenant_id)
    assert mock_repo.get_tenant_chunks.call_count == 1

    await manager.ensure_index(tenant_id)
    assert mock_repo.get_tenant_chunks.call_count == 1


@pytest.mark.asyncio
async def test_empty_tenant_zero_documents():
    """Test 3: Tenant with zero documents initializes cleanly and returns empty sparse results."""
    provider = BM25SparseSearchProvider()
    manager = SparseIndexManager(sparse_provider=provider)

    tenant_id = "tenant_empty_1"
    mock_repo = MagicMock()
    mock_repo.get_tenant_chunks = AsyncMock(return_value=[])
    manager._make_chunk_repository = MagicMock(return_value=mock_repo)

    mock_embedding = MagicMock()
    mock_embedding.embed_query = AsyncMock(return_value=[0.1] * 384)
    mock_vector = MagicMock()
    mock_vector.search_points = AsyncMock(return_value=[])
    mock_reranker = MagicMock()
    mock_reranker.rerank = AsyncMock(return_value=[])

    orchestrator = RetrievalOrchestrator(
        embedding_provider=mock_embedding,
        vector_provider=mock_vector,
        sparse_provider=provider,
        reranker_provider=mock_reranker,
        index_manager=manager,
    )

    search_req = SearchRequestDTO(query="empty query", top_k=5)
    result = await orchestrator.execute_hybrid_search(
        options=search_req,
        tenant_id=tenant_id,
        correlation_id="corr_empty",
    )

    assert manager.is_initialized(tenant_id)
    assert result.sparse_candidates_count == 0
    assert len(result.final_evidence) == 0


@pytest.mark.asyncio
async def test_concurrent_single_flight_build():
    """Test 4: Concurrent requests for an uninitialized tenant execute rebuild_index exactly ONCE."""
    provider = BM25SparseSearchProvider()
    manager = SparseIndexManager(sparse_provider=provider)

    tenant_id = "tenant_concurrent_1"
    chunk1 = _create_mock_chunk(tenant_id, "Distributed consensus via Raft algorithm.")

    mock_repo = MagicMock()
    mock_repo.get_tenant_chunks = AsyncMock(return_value=[chunk1])
    manager._make_chunk_repository = MagicMock(return_value=mock_repo)

    tasks = [manager.ensure_index(tenant_id) for _ in range(5)]
    await asyncio.gather(*tasks)

    assert mock_repo.get_tenant_chunks.call_count == 1
    assert manager.is_initialized(tenant_id)


@pytest.mark.asyncio
async def test_tenant_isolation_maintained():
    """Test 5: Tenant A queries never access Tenant B's in-memory index."""
    provider = BM25SparseSearchProvider()
    manager = SparseIndexManager(sparse_provider=provider)

    chunk_a = _create_mock_chunk("tenant_alpha", "Confidential alpha security policy.")
    chunk_b = _create_mock_chunk("tenant_bravo", "Confidential bravo financial forecast.")

    await provider.index_chunks("tenant_alpha", [chunk_a])
    await provider.index_chunks("tenant_bravo", [chunk_b])

    results = await provider.search_keywords(
        tenant_id="tenant_alpha",
        query="financial forecast",
        limit=10,
    )
    assert len(results) == 0

    results_b = await provider.search_keywords(
        tenant_id="tenant_bravo",
        query="financial forecast",
        limit=10,
    )
    assert len(results_b) == 1
    assert results_b[0].chunk_id == chunk_b.id


@pytest.mark.asyncio
async def test_document_invalidation_and_rebuild():
    """Test 6: Invalidation clears index, next search lazily re-indexes new state."""
    provider = BM25SparseSearchProvider()
    manager = SparseIndexManager(sparse_provider=provider)

    tenant_id = "tenant_inval_1"
    chunk_v1 = _create_mock_chunk(tenant_id, "Version 1 specifications.")
    chunk_v2 = _create_mock_chunk(tenant_id, "Version 2 upgraded architecture.")

    mock_repo = MagicMock()
    mock_repo.get_tenant_chunks = AsyncMock(side_effect=[[chunk_v1], [chunk_v2]])
    manager._make_chunk_repository = MagicMock(return_value=mock_repo)

    await manager.ensure_index(tenant_id)
    res1 = await provider.search_keywords(tenant_id, "specifications")
    assert len(res1) == 1

    manager.clear_index(tenant_id)
    assert not manager.is_initialized(tenant_id)

    await manager.ensure_index(tenant_id)
    res2 = await provider.search_keywords(tenant_id, "upgraded architecture")
    assert len(res2) == 1
    assert mock_repo.get_tenant_chunks.call_count == 2


@pytest.mark.asyncio
async def test_db_failure_graceful_fallback():
    """Test 7: If database fails during ensure_index, orchestrator returns empty sparse list gracefully."""
    provider = BM25SparseSearchProvider()
    manager = SparseIndexManager(sparse_provider=provider)

    tenant_id = "tenant_db_fail_1"
    mock_repo = MagicMock()
    mock_repo.get_tenant_chunks = AsyncMock(side_effect=RuntimeError("PostgreSQL connection failure"))
    manager._make_chunk_repository = MagicMock(return_value=mock_repo)

    mock_embedding = MagicMock()
    mock_embedding.embed_query = AsyncMock(return_value=[0.1] * 384)
    mock_vector = MagicMock()
    mock_vector.search_points = AsyncMock(return_value=[])
    mock_reranker = MagicMock()
    mock_reranker.rerank = AsyncMock(return_value=[])

    orchestrator = RetrievalOrchestrator(
        embedding_provider=mock_embedding,
        vector_provider=mock_vector,
        sparse_provider=provider,
        reranker_provider=mock_reranker,
        index_manager=manager,
    )

    search_req = SearchRequestDTO(query="test fallback query", top_k=5)
    result = await orchestrator.execute_hybrid_search(
        options=search_req,
        tenant_id=tenant_id,
        correlation_id="corr_fail",
    )

    assert result.sparse_candidates_count == 0
