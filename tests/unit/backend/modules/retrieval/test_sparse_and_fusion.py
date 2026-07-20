"""Unit tests for Phase 2 Milestone 4 (Hybrid Retrieval Engine) - Milestone A: Sparse Indexing & RRF Fusion."""

import uuid
from typing import Any
from unittest.mock import MagicMock

import pytest

from backend.modules.retrieval.providers.sparse.bm25_provider import (
    BM25SparseSearchProvider,
    tokenize,
)
from backend.modules.retrieval.schemas.errors import (
    ErrorSeverity,
    RetrievalErrorCode,
    SparseIndexNotFoundError,
)
from backend.modules.retrieval.schemas.retrieval_dto import (
    CandidatePointDTO,
    RankedEvidenceDTO,
)
from backend.modules.retrieval.services.fusion import (
    FusionEngine,
    compute_jaccard_similarity,
)


@pytest.fixture
def mock_chunks() -> list[MagicMock]:
    doc_id = uuid.uuid4()
    ver_id = uuid.uuid4()

    chunk1 = MagicMock()
    chunk1.id = uuid.uuid4()
    chunk1.tenant_id = "tenant_alpha"
    chunk1.document_id = doc_id
    chunk1.document_version_id = ver_id
    chunk1.chunk_index = 0
    chunk1.content = "Mutual TLS authentication requires strict certificate rotation every 90 days."
    chunk1.strategy_used = "recursive"
    chunk1.token_count = 12

    chunk2 = MagicMock()
    chunk2.id = uuid.uuid4()
    chunk2.tenant_id = "tenant_alpha"
    chunk2.document_id = doc_id
    chunk2.document_version_id = ver_id
    chunk2.chunk_index = 1
    chunk2.content = "Role-based access control enforces granular permissions across enterprise departments."
    chunk2.strategy_used = "recursive"
    chunk2.token_count = 11

    chunk3 = MagicMock()
    chunk3.id = uuid.uuid4()
    chunk3.tenant_id = "tenant_beta"
    chunk3.document_id = uuid.uuid4()
    chunk3.document_version_id = uuid.uuid4()
    chunk3.chunk_index = 0
    chunk3.content = "Tenant beta document on data encryption at rest using AES-256."
    chunk3.strategy_used = "paragraph"
    chunk3.token_count = 10

    return [chunk1, chunk2, chunk3]


@pytest.mark.asyncio
class TestBM25SparseSearchProvider:
    async def test_index_and_search_keywords(self, mock_chunks: list[MagicMock]) -> None:
        provider = BM25SparseSearchProvider()
        indexed = await provider.index_chunks("tenant_alpha", mock_chunks)
        assert indexed == 2  # Only tenant_alpha chunks

        results = await provider.search_keywords(
            tenant_id="tenant_alpha",
            query="mutual TLS certificate rotation",
            limit=10,
        )
        assert len(results) == 1
        assert results[0].chunk_id == mock_chunks[0].id
        assert results[0].source == "sparse"
        assert results[0].rank == 1
        assert results[0].score > 0.0

    async def test_search_keywords_uninitialized_tenant_raises_ret_002(self) -> None:
        provider = BM25SparseSearchProvider()
        with pytest.raises(SparseIndexNotFoundError) as exc_info:
            await provider.search_keywords("unknown_tenant", "test query")
        assert exc_info.value.code == RetrievalErrorCode.RET_002
        assert exc_info.value.severity == ErrorSeverity.FATAL

    async def test_remove_document_chunks(self, mock_chunks: list[MagicMock]) -> None:
        provider = BM25SparseSearchProvider()
        await provider.index_chunks("tenant_alpha", mock_chunks)

        doc_id_to_remove = str(mock_chunks[0].document_id)
        removed = await provider.remove_document_chunks("tenant_alpha", doc_id_to_remove)
        assert removed == 2

        results = await provider.search_keywords("tenant_alpha", "TLS authentication role access")
        assert len(results) == 0

    async def test_lru_tenant_eviction(self) -> None:
        provider = BM25SparseSearchProvider(max_tenants=2)
        chunk_mock = MagicMock()
        chunk_mock.id = uuid.uuid4()
        chunk_mock.document_id = uuid.uuid4()
        chunk_mock.document_version_id = uuid.uuid4()
        chunk_mock.chunk_index = 0
        chunk_mock.content = "test content"
        chunk_mock.strategy_used = "test"
        chunk_mock.token_count = 2

        for t in ["tenant_1", "tenant_2", "tenant_3"]:
            chunk_mock.tenant_id = t
            await provider.index_chunks(t, [chunk_mock])

        assert len(provider._indices) == 2
        assert "tenant_1" not in provider._indices
        assert "tenant_2" in provider._indices
        assert "tenant_3" in provider._indices


class TestFusionEngine:
    def test_execute_rrf_fusion_invariance_and_merging(self) -> None:
        shared_chunk_id = uuid.uuid4()
        dense_only_id = uuid.uuid4()
        sparse_only_id = uuid.uuid4()
        doc_id = uuid.uuid4()
        ver_id = uuid.uuid4()

        dense_list = [
            CandidatePointDTO(
                chunk_id=shared_chunk_id,
                document_id=doc_id,
                document_version_id=ver_id,
                tenant_id="test_org",
                content="Shared chunk content about hybrid retrieval.",
                score=0.92,
                source="dense",
                rank=1,
            ),
            CandidatePointDTO(
                chunk_id=dense_only_id,
                document_id=doc_id,
                document_version_id=ver_id,
                tenant_id="test_org",
                content="Dense only semantic match.",
                score=0.85,
                source="dense",
                rank=2,
            ),
        ]

        sparse_list = [
            CandidatePointDTO(
                chunk_id=shared_chunk_id,
                document_id=doc_id,
                document_version_id=ver_id,
                tenant_id="test_org",
                content="Shared chunk content about hybrid retrieval.",
                score=35.4,
                source="sparse",
                rank=1,
            ),
            CandidatePointDTO(
                chunk_id=sparse_only_id,
                document_id=doc_id,
                document_version_id=ver_id,
                tenant_id="test_org",
                content="Sparse exact keyword match.",
                score=28.1,
                source="sparse",
                rank=2,
            ),
        ]

        merged = FusionEngine.execute_rrf_fusion(dense_list, sparse_list, rrf_k=60)
        assert len(merged) == 3

        # Top item should be shared_chunk_id (sum of two rank 1 contributions: 1/61 + 1/61)
        assert merged[0].chunk_id == shared_chunk_id
        expected_shared_rrf = round(1.0 / 61.0 + 1.0 / 61.0, 6)
        assert merged[0].rrf_score == expected_shared_rrf
        assert merged[0].dense_rank == 1
        assert merged[0].sparse_rank == 1
        assert set(merged[0].matched_sources) == {"dense", "sparse"}
        assert merged[0].final_rank == 1

        # Ranks 2 and 3 should have score 1/62 (~0.016129)
        assert merged[1].final_rank == 2
        assert merged[2].final_rank == 3
        expected_single_rrf = round(1.0 / 62.0, 6)
        assert merged[1].rrf_score == expected_single_rrf
        assert merged[2].rrf_score == expected_single_rrf

    def test_deduplicate_candidates_near_duplicates_filtered(self) -> None:
        doc_id = uuid.uuid4()
        ver_id = uuid.uuid4()

        item1 = RankedEvidenceDTO(
            chunk_id=uuid.uuid4(),
            document_id=doc_id,
            document_version_id=ver_id,
            tenant_id="test_org",
            content="The network security firewall policy requires TLS certificate rotation every 90 days.",
            dense_rank=1,
            sparse_rank=1,
            rrf_score=0.033,
            final_rank=1,
            matched_sources=["dense", "sparse"],
        )

        # Near duplicate of item1 (Jaccard > 0.92)
        item2 = RankedEvidenceDTO(
            chunk_id=uuid.uuid4(),
            document_id=doc_id,
            document_version_id=ver_id,
            tenant_id="test_org",
            content="Network security firewall policy requires TLS certificate rotation every 90 days exactly.",
            dense_rank=2,
            sparse_rank=2,
            rrf_score=0.032,
            final_rank=2,
            matched_sources=["dense"],
        )

        # Distinct topic item
        item3 = RankedEvidenceDTO(
            chunk_id=uuid.uuid4(),
            document_id=doc_id,
            document_version_id=ver_id,
            tenant_id="test_org",
            content="Database backup verification schedule and disaster recovery protocol procedures.",
            dense_rank=3,
            sparse_rank=3,
            rrf_score=0.031,
            final_rank=3,
            matched_sources=["sparse"],
        )

        deduped = FusionEngine.deduplicate_candidates([item1, item2, item3], similarity_threshold=0.90)
        assert len(deduped) == 2
        assert deduped[0].chunk_id == item1.chunk_id
        assert deduped[0].final_rank == 1
        assert deduped[1].chunk_id == item3.chunk_id
        assert deduped[1].final_rank == 2

    def test_compute_jaccard_similarity(self) -> None:
        tokens_a = {"network", "security", "firewall", "policy"}
        tokens_b = {"network", "security", "firewall", "rules"}
        # intersection = 3, union = 5 -> 0.6
        sim = compute_jaccard_similarity(tokens_a, tokens_b)
        assert sim == 0.6
