"""Unit tests for Phase 2 Milestone 4 (Hybrid Retrieval Engine) - Phase 2: Rerankers & Orchestrator."""

from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from backend.modules.retrieval.providers.reranker.cohere_reranker import (
    CohereRerankerProvider,
)
from backend.modules.retrieval.providers.reranker.local_reranker import (
    LocalCrossEncoderProvider,
)
from backend.modules.retrieval.schemas.errors import (
    InvalidQueryError,
    RerankerTimeoutError,
    RetrievalErrorCode,
)
from backend.modules.retrieval.schemas.retrieval_dto import (
    CandidatePointDTO,
    RankedEvidenceDTO,
    SearchRequestDTO,
)
from backend.modules.retrieval.services.retrieval_service import RetrievalOrchestrator


@pytest.fixture
def mock_embedding_provider() -> MagicMock:
    provider = MagicMock()
    provider.dimension = 1536
    provider.embed_query = AsyncMock(return_value=[0.1] * 1536)
    return provider


@pytest.fixture
def mock_vector_provider() -> MagicMock:
    provider = MagicMock()
    chunk_id_1 = str(uuid.uuid4())
    chunk_id_2 = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())
    ver_id = str(uuid.uuid4())

    provider.search_points = AsyncMock(
        return_value=[
            {
                "point_id": chunk_id_1,
                "score": 0.91,
                "payload": {
                    "chunk_id": chunk_id_1,
                    "document_id": doc_id,
                    "document_version_id": ver_id,
                    "tenant_id": "org_test",
                    "content": "Dense semantic match chunk on security TLS.",
                    "metadata": {"page": 1},
                },
            },
            {
                "point_id": chunk_id_2,
                "score": 0.84,
                "payload": {
                    "chunk_id": chunk_id_2,
                    "document_id": doc_id,
                    "document_version_id": ver_id,
                    "tenant_id": "org_test",
                    "content": "Dense match chunk on firewall rotation rules.",
                    "metadata": {"page": 2},
                },
            },
        ]
    )
    return provider


@pytest.fixture
def mock_sparse_provider() -> MagicMock:
    provider = MagicMock()
    chunk_id_1 = uuid.uuid4()
    chunk_id_3 = uuid.uuid4()
    doc_id = uuid.uuid4()
    ver_id = uuid.uuid4()

    provider.search_keywords = AsyncMock(
        return_value=[
            CandidatePointDTO(
                chunk_id=chunk_id_1,
                document_id=doc_id,
                document_version_id=ver_id,
                tenant_id="org_test",
                content="Sparse keyword exact match on TLS certificate rotation.",
                score=38.5,
                source="sparse",
                rank=1,
                metadata={"page": 1},
            ),
            CandidatePointDTO(
                chunk_id=chunk_id_3,
                document_id=doc_id,
                document_version_id=ver_id,
                tenant_id="org_test",
                content="Sparse keyword match on access token expiration.",
                score=25.2,
                source="sparse",
                rank=2,
                metadata={"page": 3},
            ),
        ]
    )
    return provider


@pytest.fixture
def mock_reranker_provider() -> MagicMock:
    provider = MagicMock()
    provider.model_name = "mock-reranker"

    async def _rerank(query: str, candidates: list[RankedEvidenceDTO], top_k: int = 10) -> list[RankedEvidenceDTO]:
        out = []
        for idx, item in enumerate(candidates[:top_k], start=1):
            item.raw_rerank_score = round(1.0 - idx * 0.1, 4)
            item.final_rank = idx
            out.append(item)
        return out

    provider.rerank = AsyncMock(side_effect=_rerank)
    return provider


@pytest.mark.asyncio
class TestRetrievalOrchestrator:
    async def test_execute_hybrid_search(
        self,
        mock_embedding_provider: MagicMock,
        mock_vector_provider: MagicMock,
        mock_sparse_provider: MagicMock,
        mock_reranker_provider: MagicMock,
    ) -> None:
        orchestrator = RetrievalOrchestrator(
            embedding_provider=mock_embedding_provider,
            vector_provider=mock_vector_provider,
            sparse_provider=mock_sparse_provider,
            reranker_provider=mock_reranker_provider,
        )

        options = SearchRequestDTO(
            query="TLS certificate rotation policy",
            top_k=5,
            limit_dense=20,
            limit_sparse=20,
        )

        result = await orchestrator.execute_hybrid_search(options=options, tenant_id="org_test")

        assert result.query_text == "TLS certificate rotation policy"
        assert result.tenant_id == "org_test"
        assert result.dense_candidates_count == 2
        assert result.sparse_candidates_count == 2
        assert result.unique_candidates_merged > 0
        assert len(result.final_evidence) <= 5
        assert result.stage_latencies.total_ms > 0.0

        mock_embedding_provider.embed_query.assert_called_once_with("TLS certificate rotation policy")
        mock_vector_provider.search_points.assert_called_once()
        mock_sparse_provider.search_keywords.assert_called_once_with(
            tenant_id="org_test", query="TLS certificate rotation policy", limit=20
        )
        mock_reranker_provider.rerank.assert_called_once()

    async def test_execute_sandbox_search(
        self,
        mock_embedding_provider: MagicMock,
        mock_vector_provider: MagicMock,
        mock_sparse_provider: MagicMock,
        mock_reranker_provider: MagicMock,
    ) -> None:
        orchestrator = RetrievalOrchestrator(
            embedding_provider=mock_embedding_provider,
            vector_provider=mock_vector_provider,
            sparse_provider=mock_sparse_provider,
            reranker_provider=mock_reranker_provider,
        )

        options = SearchRequestDTO(query="Sandbox comparison test", top_k=10)
        sandbox_res = await orchestrator.execute_sandbox_search(options=options, tenant_id="org_test")

        assert len(sandbox_res.dense_results) == 2
        assert len(sandbox_res.sparse_results) == 2
        assert len(sandbox_res.rrf_merged_results) > 0
        assert len(sandbox_res.final_reranked_results) > 0

    async def test_invalid_query_raises_ret_001(
        self,
        mock_embedding_provider: MagicMock,
        mock_vector_provider: MagicMock,
        mock_sparse_provider: MagicMock,
        mock_reranker_provider: MagicMock,
    ) -> None:
        orchestrator = RetrievalOrchestrator(
            embedding_provider=mock_embedding_provider,
            vector_provider=mock_vector_provider,
            sparse_provider=mock_sparse_provider,
            reranker_provider=mock_reranker_provider,
        )

        options = SearchRequestDTO(query="   ", top_k=5)
        with pytest.raises(InvalidQueryError) as exc_info:
            await orchestrator.execute_hybrid_search(options=options, tenant_id="org_test")
        assert exc_info.value.code == RetrievalErrorCode.RET_001


@pytest.mark.asyncio
class TestRerankerProviders:
    async def test_cohere_reranker_uninitialized_raises_ret_003(self) -> None:
        provider = CohereRerankerProvider(client=None)
        item = RankedEvidenceDTO(
            chunk_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            document_version_id=uuid.uuid4(),
            tenant_id="test",
            content="test doc 1",
            rrf_score=0.5,
            final_rank=1,
        )
        item2 = RankedEvidenceDTO(
            chunk_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            document_version_id=uuid.uuid4(),
            tenant_id="test",
            content="test doc 2",
            rrf_score=0.4,
            final_rank=2,
        )
        with pytest.raises(RerankerTimeoutError) as exc_info:
            await provider.rerank("query", [item, item2])
        assert exc_info.value.code == RetrievalErrorCode.RET_003

    async def test_local_reranker_single_or_zero_candidates(self) -> None:
        provider = LocalCrossEncoderProvider()
        res_zero = await provider.rerank("query", [])
        assert res_zero == []

        item = RankedEvidenceDTO(
            chunk_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            document_version_id=uuid.uuid4(),
            tenant_id="test",
            content="single doc",
            rrf_score=0.33,
            final_rank=1,
        )
        res_one = await provider.rerank("query", [item])
        assert len(res_one) == 1
        assert res_one[0].raw_rerank_score == 0.33
        assert res_one[0].final_rank == 1
