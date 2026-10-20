"""Unit tests for Phase 4 WP-RETRIEVE Remediation.

Covers:
- RET-001: Query Rewrite Orchestrator and Strategies connected to chat pipeline
- RET-002: Fail-closed candidate validation with 1 bounded retry (100ms backoff)
- RET-003: BM25 provider multi-worker process boundary desync warning & documentation
- RET-004: Routing retrieval calls through ReliabilityGateway circuit breakers
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from backend.ai.schemas.wrapper_dto import AIWrapperRequest
from backend.ai.wrapper.service import AIWrapperService
from backend.modules.generation.schemas.generation_dto import StreamingGenerationChunkDTO
from backend.modules.query_rewrite.schemas.rewrite_dto import (
    RewriteRequestDTOv2,
    RewriteResultDTO,
    RewriteStrategy,
)
from backend.modules.query_rewrite.services.rewrite_orchestrator import RewriteOrchestrator
from backend.modules.reliability.circuit_breaker.engine import CircuitBreakerEngine
from backend.modules.reliability.fallbacks.router import FallbackRouter
from backend.modules.reliability.fallbacks.zero_result import ZeroResultRecoverer
from backend.modules.reliability.schemas.reliability_dto import (
    ReliableCandidateDTO,
    ReliableRetrievalResultDTO,
    SearchOptionsDTO,
)
from backend.modules.reliability.services.reliability_gateway import ReliabilityGateway
from backend.modules.retrieval.providers.sparse.bm25_provider import BM25SparseSearchProvider
from backend.modules.retrieval.schemas.retrieval_dto import (
    RankedEvidenceDTO,
    RetrievalResultDTO,
    SearchRequestDTO,
)
from backend.modules.retrieval.services.retrieval_service import RetrievalOrchestrator


class TestWPRetrieveRemediation:
    """Test suite validating all Phase 4 WP-RETRIEVE findings."""

    # -------------------------------------------------------------------------
    # RET-001: Query Rewrite Orchestrator in Chat
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_ret_001_chat_invokes_rewrite_orchestrator(self):
        """RET-001: Conversation history triggers RewriteOrchestrator and updates retrieval_query."""
        mock_ns = AsyncMock()
        mock_ns.resolve.return_value = MagicMock(collection_name="test_col")

        mock_gateway = AsyncMock()
        mock_gateway.execute_reliable_search.return_value = ReliableRetrievalResultDTO(
            query_text="What are PostgreSQL acid transactions?",
            tenant_id="tenant-1",
            correlation_id="corr-ret-1",
            candidates=[],
            duration_ms=12.0,
        )

        mock_rewrite = MagicMock(spec=RewriteOrchestrator)
        mock_rewrite.rewrite.return_value = RewriteResultDTO(
            original_query="What are its acid transactions?",
            rewritten_query="What are PostgreSQL acid transactions?",
            strategy=RewriteStrategy.ENTITY_RECOVERY,
            confidence=0.95,
            rationale="Resolved pronoun to PostgreSQL",
        )

        mock_gen = MagicMock()
        async def mock_stream(_req):
            yield StreamingGenerationChunkDTO(
                chunk_index=0,
                text_delta="Answer",
                is_final=True,
                correlation_id="corr-ret-1",
            )
        mock_gen.generate_stream = mock_stream

        wrapper = AIWrapperService(
            namespace_resolver=mock_ns,
            rate_limiter=AsyncMock(),
            retrieval_orchestrator=AsyncMock(),
            streaming_generation=mock_gen,
            event_dispatcher=AsyncMock(),
            llm_manager=MagicMock(),
            reliability_gateway=mock_gateway,
            query_rewrite_orchestrator=mock_rewrite,
        )
        wrapper._validate_workspace = AsyncMock()

        req = AIWrapperRequest(
            workspace_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            query="What are its acid transactions?",
            conversation_history=[
                {"role": "user", "content": "Tell me about PostgreSQL."},
                {"role": "assistant", "content": "PostgreSQL is a relational database."},
            ],
        )

        chunks = []
        async for chunk in wrapper.stream_request(req, user_id=uuid.uuid4(), correlation_id="corr-ret-1"):
            chunks.append(chunk)

        assert len(chunks) == 1
        # Verify RewriteOrchestrator was called
        mock_rewrite.rewrite.assert_called_once()
        rewrite_call_arg = mock_rewrite.rewrite.call_args[0][0]
        assert isinstance(rewrite_call_arg, RewriteRequestDTOv2)
        assert rewrite_call_arg.original_query == "What are its acid transactions?"

        # Verify reliable search used the rewritten query
        mock_gateway.execute_reliable_search.assert_called_once()
        assert mock_gateway.execute_reliable_search.call_args.kwargs["query"] == "What are PostgreSQL acid transactions?"

    @pytest.mark.asyncio
    async def test_ret_001_chat_rewrite_failure_gracefully_falls_back(self):
        """RET-001: Failure during query rewriting logs warning and falls back to original query."""
        mock_ns = AsyncMock()
        mock_ns.resolve.return_value = MagicMock(collection_name="test_col")

        mock_gateway = AsyncMock()
        mock_gateway.execute_reliable_search.return_value = ReliableRetrievalResultDTO(
            query_text="Original query",
            tenant_id="tenant-1",
            correlation_id="corr-ret-2",
            candidates=[],
            duration_ms=10.0,
        )

        mock_rewrite = MagicMock(spec=RewriteOrchestrator)
        mock_rewrite.rewrite.side_effect = RuntimeError("Rewrite engine timeout")

        mock_gen = MagicMock()
        async def mock_stream(_req):
            yield StreamingGenerationChunkDTO(
                chunk_index=0,
                text_delta="Answer",
                is_final=True,
                correlation_id="corr-ret-2",
            )
        mock_gen.generate_stream = mock_stream

        wrapper = AIWrapperService(
            namespace_resolver=mock_ns,
            rate_limiter=AsyncMock(),
            retrieval_orchestrator=AsyncMock(),
            streaming_generation=mock_gen,
            event_dispatcher=AsyncMock(),
            llm_manager=MagicMock(),
            reliability_gateway=mock_gateway,
            query_rewrite_orchestrator=mock_rewrite,
        )
        wrapper._validate_workspace = AsyncMock()

        req = AIWrapperRequest(
            workspace_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            query="Original query",
            conversation_history=[{"role": "user", "content": "Prior message"}],
        )

        chunks = []
        async for chunk in wrapper.stream_request(req, user_id=uuid.uuid4(), correlation_id="corr-ret-2"):
            chunks.append(chunk)

        assert len(chunks) == 1
        # Fallback to original query
        assert mock_gateway.execute_reliable_search.call_args.kwargs["query"] == "Original query"

    # -------------------------------------------------------------------------
    # RET-002: Fail-Closed Candidate Validation with Bounded Retry
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_ret_002_validate_active_candidates_transient_retry_succeeds(self):
        """RET-002: Transient error in validate_active_candidates retries after 100ms and succeeds."""
        cid = uuid.uuid4()
        did = uuid.uuid4()
        dvid = uuid.uuid4()

        candidate = RankedEvidenceDTO(
            chunk_id=cid,
            document_id=did,
            document_version_id=dvid,
            tenant_id="tenant-1",
            content="Evidence chunk text",
            rrf_score=0.9,
            final_rank=1,
        )

        mock_repo = MagicMock()
        # First attempt fails, second succeeds
        mock_repo.validate_active_candidates = AsyncMock(
            side_effect=[
                RuntimeError("Transient DB connection glitch"),
                {(cid, did, dvid)},
            ]
        )

        mock_reranker = AsyncMock()
        mock_reranker.rerank.side_effect = lambda query, candidates, top_k: candidates[:top_k]

        orchestrator = RetrievalOrchestrator(
            embedding_provider=MagicMock(),
            vector_provider=MagicMock(),
            sparse_provider=MagicMock(),
            reranker_provider=mock_reranker,
            repository=mock_repo,
        )

        from backend.modules.retrieval.services.fusion import FusionEngine

        with patch.object(orchestrator, "_execute_dense_stage", new_callable=AsyncMock) as m_dense, \
             patch.object(orchestrator, "_execute_sparse_stage", new_callable=AsyncMock) as m_sparse, \
             patch.object(FusionEngine, "execute_rrf_fusion", return_value=[candidate]), \
             patch.object(FusionEngine, "deduplicate_candidates", return_value=[candidate]):
            m_dense.return_value = ([], 1.0)
            m_sparse.return_value = ([], 1.0)

            req = SearchRequestDTO(query="test", top_k=5)
            result = await orchestrator.execute_hybrid_search(
                options=req,
                tenant_id="tenant-1",
                correlation_id="corr-ret-3",
            )

            assert mock_repo.validate_active_candidates.call_count == 2
            assert len(result.final_evidence) == 1
            assert result.final_evidence[0].chunk_id == cid

    @pytest.mark.asyncio
    async def test_ret_002_validate_active_candidates_persistent_failure_fails_closed(self):
        """RET-002: Persistent failure strictly fails closed: candidates wiped, metric incremented."""
        cid = uuid.uuid4()
        did = uuid.uuid4()
        dvid = uuid.uuid4()

        candidate = RankedEvidenceDTO(
            chunk_id=cid,
            document_id=did,
            document_version_id=dvid,
            tenant_id="tenant-1",
            content="Evidence chunk text",
            rrf_score=0.9,
            final_rank=1,
        )

        mock_repo = MagicMock()
        # Both attempts fail
        mock_repo.validate_active_candidates = AsyncMock(
            side_effect=[
                RuntimeError("DB error attempt 1"),
                RuntimeError("DB error attempt 2"),
            ]
        )

        mock_reranker = AsyncMock()
        mock_reranker.rerank.side_effect = lambda query, candidates, top_k: candidates[:top_k]

        orchestrator = RetrievalOrchestrator(
            embedding_provider=MagicMock(),
            vector_provider=MagicMock(),
            sparse_provider=MagicMock(),
            reranker_provider=mock_reranker,
            repository=mock_repo,
        )

        from backend.modules.retrieval.services.fusion import FusionEngine

        with patch.object(orchestrator, "_execute_dense_stage", new_callable=AsyncMock) as m_dense, \
             patch.object(orchestrator, "_execute_sparse_stage", new_callable=AsyncMock) as m_sparse, \
             patch.object(FusionEngine, "execute_rrf_fusion", return_value=[candidate]), \
             patch.object(FusionEngine, "deduplicate_candidates", return_value=[candidate]):
            m_dense.return_value = ([], 1.0)
            m_sparse.return_value = ([], 1.0)

            req = SearchRequestDTO(query="test", top_k=5)
            result = await orchestrator.execute_hybrid_search(
                options=req,
                tenant_id="tenant-1",
                correlation_id="corr-ret-4",
            )

            assert mock_repo.validate_active_candidates.call_count == 2
            # Strictly fail-closed: final evidence is empty
            assert len(result.final_evidence) == 0

    @pytest.mark.asyncio
    async def test_ret_002_filter_active_ready_document_ids_transient_retry(self):
        """RET-002: Fallback filter_active_ready_document_ids retries on transient error and succeeds."""
        cid = uuid.uuid4()
        did = uuid.uuid4()
        dvid = uuid.uuid4()

        candidate = RankedEvidenceDTO(
            chunk_id=cid,
            document_id=did,
            document_version_id=dvid,
            tenant_id="tenant-1",
            content="Evidence chunk text",
            rrf_score=0.9,
            final_rank=1,
        )

        class LegacyRepo:
            def __init__(self):
                self.filter_active_ready_document_ids = AsyncMock(
                    side_effect=[
                        RuntimeError("Transient error"),
                        {did},
                    ]
                )

        mock_repo = LegacyRepo()
        mock_reranker = AsyncMock()
        mock_reranker.rerank.side_effect = lambda query, candidates, top_k: candidates[:top_k]

        orchestrator = RetrievalOrchestrator(
            embedding_provider=MagicMock(),
            vector_provider=MagicMock(),
            sparse_provider=MagicMock(),
            reranker_provider=mock_reranker,
            repository=mock_repo,
        )

        from backend.modules.retrieval.services.fusion import FusionEngine

        with patch.object(orchestrator, "_execute_dense_stage", new_callable=AsyncMock) as m_dense, \
             patch.object(orchestrator, "_execute_sparse_stage", new_callable=AsyncMock) as m_sparse, \
             patch.object(FusionEngine, "execute_rrf_fusion", return_value=[candidate]), \
             patch.object(FusionEngine, "deduplicate_candidates", return_value=[candidate]):
            m_dense.return_value = ([], 1.0)
            m_sparse.return_value = ([], 1.0)

            req = SearchRequestDTO(query="test", top_k=5)
            result = await orchestrator.execute_hybrid_search(
                options=req,
                tenant_id="tenant-1",
                correlation_id="corr-ret-5",
            )

            assert mock_repo.filter_active_ready_document_ids.call_count == 2
            assert len(result.final_evidence) == 1
            assert result.final_evidence[0].document_id == did

    @pytest.mark.asyncio
    async def test_ret_002_filter_active_ready_document_ids_persistent_failure_fails_closed(self):
        """RET-002: Fallback filter_active_ready_document_ids strictly fails closed on persistent error."""
        cid = uuid.uuid4()
        did = uuid.uuid4()
        dvid = uuid.uuid4()

        candidate = RankedEvidenceDTO(
            chunk_id=cid,
            document_id=did,
            document_version_id=dvid,
            tenant_id="tenant-1",
            content="Evidence chunk text",
            rrf_score=0.9,
            final_rank=1,
        )

        class LegacyRepo:
            def __init__(self):
                self.filter_active_ready_document_ids = AsyncMock(
                    side_effect=[
                        RuntimeError("Persistent error 1"),
                        RuntimeError("Persistent error 2"),
                    ]
                )

        mock_repo = LegacyRepo()
        mock_reranker = AsyncMock()
        mock_reranker.rerank.side_effect = lambda query, candidates, top_k: candidates[:top_k]

        orchestrator = RetrievalOrchestrator(
            embedding_provider=MagicMock(),
            vector_provider=MagicMock(),
            sparse_provider=MagicMock(),
            reranker_provider=mock_reranker,
            repository=mock_repo,
        )

        from backend.modules.retrieval.services.fusion import FusionEngine

        with patch.object(orchestrator, "_execute_dense_stage", new_callable=AsyncMock) as m_dense, \
             patch.object(orchestrator, "_execute_sparse_stage", new_callable=AsyncMock) as m_sparse, \
             patch.object(FusionEngine, "execute_rrf_fusion", return_value=[candidate]), \
             patch.object(FusionEngine, "deduplicate_candidates", return_value=[candidate]):
            m_dense.return_value = ([], 1.0)
            m_sparse.return_value = ([], 1.0)

            req = SearchRequestDTO(query="test", top_k=5)
            result = await orchestrator.execute_hybrid_search(
                options=req,
                tenant_id="tenant-1",
                correlation_id="corr-ret-6",
            )

            assert mock_repo.filter_active_ready_document_ids.call_count == 2
            assert len(result.final_evidence) == 0

    # -------------------------------------------------------------------------
    # RET-003: BM25 Multi-Worker Process Boundary Warning
    # -------------------------------------------------------------------------

    def test_ret_003_bm25_single_worker_no_warning(self):
        """RET-003: When WEB_CONCURRENCY=1 and CELERY_CONCURRENCY=1, no multi-worker warning is logged."""
        with patch.dict("os.environ", {"WEB_CONCURRENCY": "1", "CELERY_CONCURRENCY": "1"}):
            with patch("backend.modules.retrieval.providers.sparse.bm25_provider.logger.warning") as m_warn:
                provider = BM25SparseSearchProvider()
                assert provider is not None
                m_warn.assert_not_called()

    def test_ret_003_bm25_multi_worker_logs_warning(self):
        """RET-003: When WEB_CONCURRENCY > 1 or CELERY_CONCURRENCY > 1, warning is logged."""
        with patch.dict("os.environ", {"WEB_CONCURRENCY": "4", "CELERY_CONCURRENCY": "1"}):
            with patch("backend.modules.retrieval.providers.sparse.bm25_provider.logger.warning") as m_warn:
                provider = BM25SparseSearchProvider()
                assert provider is not None
                m_warn.assert_called_once()
                warning_msg = m_warn.call_args[0][0]
                assert "RET-003" in warning_msg
                assert "multi-worker configuration" in warning_msg

        with patch.dict("os.environ", {"WEB_CONCURRENCY": "1", "CELERY_CONCURRENCY": "2"}):
            with patch("backend.modules.retrieval.providers.sparse.bm25_provider.logger.warning") as m_warn:
                provider = BM25SparseSearchProvider()
                assert provider is not None
                m_warn.assert_called_once()
                warning_msg = m_warn.call_args[0][0]
                assert "RET-003" in warning_msg

    def test_ret_003_bm25_architectural_docstring_present(self):
        """RET-003: BM25SparseSearchProvider docstring documents the architectural boundary limitation."""
        doc = BM25SparseSearchProvider.__doc__ or ""
        assert "RET-003 Architectural Policy" in doc
        assert "multi-worker deployments" in doc
        assert "process boundaries" in doc

    # -------------------------------------------------------------------------
    # RET-004: ReliabilityGateway Circuit Breakers in Chat
    # -------------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_ret_004_ai_wrapper_routes_search_through_reliability_gateway(self):
        """RET-004: AIWrapperService routes search through ReliabilityGateway.execute_reliable_search."""
        mock_ns = AsyncMock()
        mock_ns.resolve.return_value = MagicMock(collection_name="col_test")

        cid = uuid.uuid4()
        did = uuid.uuid4()
        dvid = uuid.uuid4()

        candidate = ReliableCandidateDTO(
            chunk_id=str(cid),
            document_id=str(did),
            document_version_id=str(dvid),
            tenant_id="tenant-gate",
            content="Grounded content from reliability gateway",
            score=0.92,
            rank=1,
        )

        mock_gateway = AsyncMock(spec=ReliabilityGateway)
        mock_gateway.execute_reliable_search.return_value = ReliableRetrievalResultDTO(
            query_text="search query",
            tenant_id="tenant-gate",
            correlation_id="corr-gate-1",
            candidates=[candidate],
            duration_ms=45.0,
            is_sla_breached=False,
        )

        mock_gen = MagicMock()
        async def mock_stream(gen_req):
            assert len(gen_req.evidence_chunks) == 1
            assert gen_req.evidence_chunks[0].chunk_id == cid
            assert gen_req.evidence_chunks[0].content == "Grounded content from reliability gateway"
            yield StreamingGenerationChunkDTO(
                chunk_index=0,
                text_delta="Grounded response",
                is_final=True,
                correlation_id="corr-gate-1",
            )
        mock_gen.generate_stream = mock_stream

        mock_dispatcher = AsyncMock()

        wrapper = AIWrapperService(
            namespace_resolver=mock_ns,
            rate_limiter=AsyncMock(),
            retrieval_orchestrator=AsyncMock(),
            streaming_generation=mock_gen,
            event_dispatcher=mock_dispatcher,
            llm_manager=MagicMock(),
            reliability_gateway=mock_gateway,
        )
        wrapper._validate_workspace = AsyncMock()

        req = AIWrapperRequest(
            workspace_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            query="search query",
        )

        chunks = []
        async for chunk in wrapper.stream_request(req, user_id=uuid.uuid4(), correlation_id="corr-gate-1"):
            chunks.append(chunk)

        assert len(chunks) == 1
        mock_gateway.execute_reliable_search.assert_called_once()
        call_kwargs = mock_gateway.execute_reliable_search.call_args.kwargs
        assert call_kwargs["query"] == "search query"
        assert isinstance(call_kwargs["options"], SearchOptionsDTO)
        assert call_kwargs["options"].sla_budget_ms == 5000.0

    @pytest.mark.asyncio
    async def test_ret_004_ai_wrapper_default_gateway_construction(self):
        """RET-004: When reliability_gateway is None, AIWrapperService auto-constructs a ReliabilityGateway."""
        mock_retrieval = AsyncMock()

        wrapper = AIWrapperService(
            namespace_resolver=AsyncMock(),
            rate_limiter=AsyncMock(),
            retrieval_orchestrator=mock_retrieval,
            streaming_generation=AsyncMock(),
            event_dispatcher=AsyncMock(),
            llm_manager=MagicMock(),
        )

        assert wrapper.reliability_gateway is not None
        assert isinstance(wrapper.reliability_gateway, ReliabilityGateway)
        assert wrapper.reliability_gateway.orchestrator == mock_retrieval

    @pytest.mark.asyncio
    async def test_ret_004_ai_wrapper_fallback_to_orchestrator_when_gateway_none(self):
        """RET-004: When reliability_gateway is explicitly None, fallback to execute_hybrid_search."""
        mock_retrieval = AsyncMock()
        mock_retrieval.execute_hybrid_search.return_value = MagicMock(final_evidence=[])

        wrapper = AIWrapperService(
            namespace_resolver=AsyncMock(),
            rate_limiter=AsyncMock(),
            retrieval_orchestrator=mock_retrieval,
            streaming_generation=AsyncMock(),
            event_dispatcher=AsyncMock(),
            llm_manager=MagicMock(),
        )
        # Explicitly set reliability_gateway to None
        wrapper.reliability_gateway = None
        wrapper._validate_workspace = AsyncMock()

        mock_ns = AsyncMock()
        mock_ns.resolve.return_value = MagicMock(collection_name="col_test")
        wrapper.namespace_resolver = mock_ns

        mock_gen = MagicMock()
        async def mock_stream(_req):
            yield StreamingGenerationChunkDTO(
                chunk_index=0,
                text_delta="text",
                is_final=True,
                correlation_id="corr-none",
            )
        mock_gen.generate_stream = mock_stream
        wrapper.streaming_generation = mock_gen

        req = AIWrapperRequest(
            workspace_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            query="test",
        )

        chunks = []
        async for chunk in wrapper.stream_request(req, user_id=uuid.uuid4(), correlation_id="corr-none"):
            chunks.append(chunk)

        assert len(chunks) == 1
        mock_retrieval.execute_hybrid_search.assert_called_once()
