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

    async def test_tenant_isolation_caller_collection_name_override_ignored(
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

        from backend.modules.retrieval.schemas.filter_dsl import FilterDSL

        # Attacker supplies collection_name and victim tenant_id inside filter_dsl
        dsl = FilterDSL(
            tenant_id="victim_tenant",
            metadata_eq={"category": "confidential"}
        )
        options = SearchRequestDTO(
            query="sensitive data exfiltration",
            top_k=5,
            filter_dsl=dsl,
        )

        await orchestrator.execute_hybrid_search(options=options, tenant_id="attacker_tenant")

        # Must query attacker's collection strictly and use attacker_tenant
        mock_vector_provider.search_points.assert_called_once()
        call_kwargs = mock_vector_provider.search_points.call_args.kwargs
        assert call_kwargs["collection_name"] == "raguard_knowledge_attacker_tenant"
        assert call_kwargs["filter_conditions"]["tenant_id"] == "attacker_tenant"
        assert "collection_name" not in call_kwargs["filter_conditions"]

    async def test_tenant_isolation_caller_tenant_id_in_filters_cannot_override(
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

        from backend.modules.retrieval.schemas.filter_dsl import FilterDSL

        # Attacker tries to pass tenant_id in FilterDSL
        dsl = FilterDSL(tenant_id="other_tenant")
        options = SearchRequestDTO(
            query="test tenant filter tampering",
            top_k=5,
            filter_dsl=dsl,
        )

        await orchestrator.execute_hybrid_search(options=options, tenant_id="trusted_tenant")

        mock_vector_provider.search_points.assert_called_once()
        call_kwargs = mock_vector_provider.search_points.call_args.kwargs
        assert call_kwargs["filter_conditions"]["tenant_id"] == "trusted_tenant"

    async def test_sandbox_search_resolves_tenant_collection_strictly(
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

        options = SearchRequestDTO(query="Sandbox multi-stage evaluation", top_k=5)

        sandbox_res = await orchestrator.execute_sandbox_search(options=options, tenant_id="tenant_sandbox_123")

        mock_vector_provider.search_points.assert_called_once()
        call_kwargs = mock_vector_provider.search_points.call_args.kwargs
        assert call_kwargs["collection_name"] == "raguard_knowledge_tenant_sandbox_123"
        assert call_kwargs["filter_conditions"]["tenant_id"] == "tenant_sandbox_123"
        assert len(sandbox_res.dense_results) == 2

    async def test_candidate_validation_rejects_superseded_or_inactive_versions(
        self,
        mock_embedding_provider: MagicMock,
        mock_sparse_provider: MagicMock,
        mock_reranker_provider: MagicMock,
    ) -> None:
        valid_cid = uuid.uuid4()
        stale_cid = uuid.uuid4()
        doc_id = uuid.uuid4()
        v1_id = uuid.uuid4()
        v2_id = uuid.uuid4()

        vector_prov = MagicMock()
        vector_prov.search_points = AsyncMock(
            return_value=[
                {
                    "point_id": str(valid_cid),
                    "score": 0.95,
                    "payload": {
                        "chunk_id": str(valid_cid),
                        "document_id": str(doc_id),
                        "document_version_id": str(v2_id),
                        "tenant_id": "test_tenant",
                        "content": "Active version 2 content",
                    },
                },
                {
                    "point_id": str(stale_cid),
                    "score": 0.92,
                    "payload": {
                        "chunk_id": str(stale_cid),
                        "document_id": str(doc_id),
                        "document_version_id": str(v1_id),
                        "tenant_id": "test_tenant",
                        "content": "Superseded version 1 content",
                    },
                },
            ]
        )

        mock_repo = MagicMock()
        # Mock repository validating ONLY (valid_cid, doc_id, v2_id) as active
        mock_repo.validate_active_candidates = AsyncMock(
            return_value={(valid_cid, doc_id, v2_id)}
        )

        # Sparse returns empty to isolate dense candidate validation
        sparse_prov = MagicMock()
        sparse_prov.search_keywords = AsyncMock(return_value=[])

        orchestrator = RetrievalOrchestrator(
            embedding_provider=mock_embedding_provider,
            vector_provider=vector_prov,
            sparse_provider=sparse_prov,
            reranker_provider=mock_reranker_provider,
            repository=mock_repo,
        )

        options = SearchRequestDTO(query="test version validation", top_k=5)
        res = await orchestrator.execute_hybrid_search(options=options, tenant_id="test_tenant")

        # Stale candidate must be discarded before reranking
        mock_repo.validate_active_candidates.assert_called_once()
        reranked_chunks = [c.chunk_id for c in res.final_evidence]
        assert valid_cid in reranked_chunks
        assert stale_cid not in reranked_chunks

    async def test_dense_overfetch_supplemental_timeout_preserves_primary_results(
        self,
        mock_embedding_provider: MagicMock,
        mock_sparse_provider: MagicMock,
        mock_reranker_provider: MagicMock,
    ) -> None:
        """D4-2: When primary call completes but supplemental over-fetch times out, primary results must survive."""
        primary_cids = [uuid.uuid4() for _ in range(10)]
        doc_id = uuid.uuid4()
        ver_id = uuid.uuid4()
        tenant_id = "tenant_timeout_test"

        vector_prov = MagicMock()
        primary_hits = [
            {
                "point_id": str(cid),
                "score": 0.95 - i * 0.01,
                "payload": {
                    "chunk_id": str(cid),
                    "document_id": str(doc_id),
                    "document_version_id": str(ver_id),
                    "tenant_id": tenant_id,
                    "content": f"Distinct scientific domain subject matter {i} analyzing topic {uuid.uuid4().hex}",
                },
            }
            for i, cid in enumerate(primary_cids)
        ]

        # Call 1 returns primary_hits; Call 2 times out
        async def _mock_search(*args, **kwargs):
            if kwargs.get("offset") is None:
                return list(primary_hits)
            raise TimeoutError("Supplementary overfetch timeout")

        vector_prov.search_points = AsyncMock(side_effect=_mock_search)

        mock_repo = MagicMock()
        mock_repo.validate_active_candidates = AsyncMock(
            return_value={(cid, doc_id, ver_id) for cid in primary_cids}
        )

        sparse_prov = MagicMock()
        sparse_prov.search_keywords = AsyncMock(return_value=[])

        orchestrator = RetrievalOrchestrator(
            embedding_provider=mock_embedding_provider,
            vector_provider=vector_prov,
            sparse_provider=sparse_prov,
            reranker_provider=mock_reranker_provider,
            repository=mock_repo,
        )

        # Set limit_dense=10 (valid >=10) to trigger supplementary over-fetch (len(hits) == limit)
        options = SearchRequestDTO(query="timeout resilience test", top_k=10, limit_dense=10)
        res = await orchestrator.execute_hybrid_search(options=options, tenant_id=tenant_id)

        # Both calls were attempted
        assert vector_prov.search_points.call_count == 2
        # Candidate validation ran on preserved primary hits
        mock_repo.validate_active_candidates.assert_called_once()
        # Primary results survived into final evidence
        final_cids = [c.chunk_id for c in res.final_evidence]
        assert len(final_cids) == 10
        assert primary_cids[0] in final_cids

    async def test_dense_primary_timeout_yields_empty_candidates_no_fabrication(
        self,
        mock_embedding_provider: MagicMock,
        mock_sparse_provider: MagicMock,
        mock_reranker_provider: MagicMock,
    ) -> None:
        """D4-2: When primary call itself times out, no nonexistent results are fabricated."""
        vector_prov = MagicMock()
        vector_prov.search_points = AsyncMock(side_effect=TimeoutError("Primary search timeout"))

        sparse_prov = MagicMock()
        sparse_prov.search_keywords = AsyncMock(return_value=[])

        orchestrator = RetrievalOrchestrator(
            embedding_provider=mock_embedding_provider,
            vector_provider=vector_prov,
            sparse_provider=sparse_prov,
            reranker_provider=mock_reranker_provider,
        )

        options = SearchRequestDTO(query="primary timeout test", top_k=5)
        res = await orchestrator.execute_hybrid_search(options=options, tenant_id="tenant_p_timeout")

        # Vector search was attempted once
        assert vector_prov.search_points.call_count == 1
        # No results fabricated
        assert len(res.final_evidence) == 0

    async def test_dense_overfetch_supplemental_success_merges_and_deduplicates(
        self,
        mock_embedding_provider: MagicMock,
        mock_sparse_provider: MagicMock,
        mock_reranker_provider: MagicMock,
    ) -> None:
        """D4-2: Supplemental call succeeds, merges new results, and deduplicates against primary results."""
        primary_cids = [uuid.uuid4() for _ in range(10)]
        supp_cid = uuid.uuid4()
        doc_id = uuid.uuid4()
        ver_id = uuid.uuid4()
        tenant_id = "tenant_overfetch_test"

        primary_hits = [
            {
                "point_id": str(cid),
                "score": 0.95 - i * 0.01,
                "payload": {
                    "chunk_id": str(cid),
                    "document_id": str(doc_id),
                    "document_version_id": str(ver_id),
                    "tenant_id": tenant_id,
                    "content": f"Discrete distinct knowledge fragment {i} analyzing concept {uuid.uuid4().hex}",
                },
            }
            for i, cid in enumerate(primary_cids)
        ]
        supp_hits = [
            {
                "point_id": str(supp_cid),
                "score": 0.80,
                "payload": {
                    "chunk_id": str(supp_cid),
                    "document_id": str(doc_id),
                    "document_version_id": str(ver_id),
                    "tenant_id": tenant_id,
                    "content": f"Unique supplementary knowledge discovery topic {uuid.uuid4().hex}",
                },
            },
            primary_hits[0],  # Duplicate of first primary hit
        ]

        # Call 1 returns primary_hits (limit=10). Call 2 returns supp_hits (1 new, 1 duplicate).
        async def _mock_search(*args, **kwargs):
            if kwargs.get("offset") is None:
                return list(primary_hits)
            return list(supp_hits)

        vector_prov = MagicMock()
        vector_prov.search_points = AsyncMock(side_effect=_mock_search)

        mock_repo = MagicMock()
        mock_repo.validate_active_candidates = AsyncMock(
            return_value={(cid, doc_id, ver_id) for cid in primary_cids} | {(supp_cid, doc_id, ver_id)}
        )

        sparse_prov = MagicMock()
        sparse_prov.search_keywords = AsyncMock(return_value=[])

        orchestrator = RetrievalOrchestrator(
            embedding_provider=mock_embedding_provider,
            vector_provider=vector_prov,
            sparse_provider=sparse_prov,
            reranker_provider=mock_reranker_provider,
            repository=mock_repo,
        )

        options = SearchRequestDTO(query="overfetch merge test", top_k=15, limit_dense=10)
        res = await orchestrator.execute_hybrid_search(options=options, tenant_id=tenant_id)

        # Verified two calls made, second with offset=10
        assert vector_prov.search_points.call_count == 2
        second_call_kwargs = vector_prov.search_points.call_args_list[1].kwargs
        assert second_call_kwargs["offset"] == 10

        # Verified all 11 unique chunks validated without duplicate
        final_cids = [c.chunk_id for c in res.final_evidence]
        assert len(final_cids) == 11
        assert supp_cid in final_cids
        assert primary_cids[0] in final_cids


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
