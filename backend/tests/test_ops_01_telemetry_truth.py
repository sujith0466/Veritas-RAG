import uuid
from datetime import UTC, datetime
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from backend.database.engine import get_session_factory
from backend.modules.analytics.models.query_analytics import QueryAnalyticsRecord
from backend.modules.analytics.repositories.analytics_repository import AnalyticsRepository
from backend.modules.analytics.schemas.analytics_dto import (
    QuerySandboxRequestDTO,
    QueryTraceDetailDTO,
    StageTraceDTO,
)
from backend.modules.analytics.services.analytics_service import QueryAnalyticsService
from backend.modules.retrieval.models.retrieval_log import RetrievalQueryLog


@pytest.mark.asyncio
async def test_stage_trace_dto_is_authoritative_contract():
    """Verify DTO contract for is_authoritative across StageTraceDTO and QueryTraceDetailDTO."""
    st = StageTraceDTO(
        stage_name="Test Stage",
        duration_ms=45.2,
        status="COMPLETED",
        is_authoritative=True,
    )
    assert st.is_authoritative is True

    st_est = StageTraceDTO(
        stage_name="Test Stage",
        duration_ms=45.2,
        status="COMPLETED",
        is_authoritative=False,
    )
    assert st_est.is_authoritative is False


@pytest.mark.asyncio
async def test_get_query_trace_detail_authoritative_with_retrieval_log():
    """Verify that when a RetrievalQueryLog exists, trace details are authoritative with hardware timings."""
    tenant_id = f"test-tenant-{uuid.uuid4()}"
    correlation_id = str(uuid.uuid4())

    async with get_session_factory()() as session:
        # Insert base query analytics record
        record = QueryAnalyticsRecord(
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            query_text="What is Veritas RAG architecture?",
            outcome="SUCCESS",
            total_duration_ms=150.0,
            confidence_score=0.92,
            reliability_score=0.92,
            retry_attempts=0,
            is_safe_to_serve=True,
            created_at=datetime.now(UTC),
        )
        session.add(record)

        # Insert matching authoritative retrieval query log
        retrieval_log = RetrievalQueryLog(
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            query_text="What is Veritas RAG architecture?",
            dense_candidate_count=20,
            sparse_candidate_count=10,
            merged_unique_count=25,
            final_top_k=5,
            total_duration_ms=85.0,
            stage_breakdown_json={
                "dense_ms": 42.5,
                "sparse_ms": 12.3,
                "rrf_fusion_ms": 3.2,
                "rerank_ms": 27.0,
            },
        )
        session.add(retrieval_log)
        await session.commit()

        repo = AnalyticsRepository(session)
        service = QueryAnalyticsService(repo)

        trace_detail = await service.get_query_trace_detail(
            correlation_id=correlation_id, tenant_id=tenant_id
        )

        assert trace_detail.is_authoritative is True
        assert len(trace_detail.stage_traces) == 5

        # Check stage names and authoritative flag
        stage_names = [s.stage_name for s in trace_detail.stage_traces]
        assert "Dense Vector Search (Qdrant)" in stage_names
        assert "Sparse Keyword Search (BM25)" in stage_names
        assert "Reciprocal Rank Fusion (RRF)" in stage_names
        assert "Cross-Encoder Reranking" in stage_names
        assert "LLM Generation & Verification" in stage_names

        dense_stage = next(s for s in trace_detail.stage_traces if s.stage_name == "Dense Vector Search (Qdrant)")
        assert dense_stage.duration_ms == 42.5
        assert dense_stage.is_authoritative is True
        assert dense_stage.metadata["candidates_retrieved"] == 20

        sparse_stage = next(s for s in trace_detail.stage_traces if s.stage_name == "Sparse Keyword Search (BM25)")
        assert sparse_stage.duration_ms == 12.3
        assert sparse_stage.is_authoritative is True

        llm_stage = next(s for s in trace_detail.stage_traces if s.stage_name == "LLM Generation & Verification")
        assert llm_stage.is_authoritative is True
        # Total was 150.0, retrieval measured was 85.0 -> LLM is 65.0
        assert llm_stage.duration_ms == 65.0


@pytest.mark.asyncio
async def test_get_query_trace_detail_fallback_without_retrieval_log():
    """Verify fallback path: when RetrievalQueryLog is missing, is_authoritative is False and stages are marked estimated."""
    tenant_id = f"test-tenant-{uuid.uuid4()}"
    correlation_id = str(uuid.uuid4())

    async with get_session_factory()() as session:
        # Insert record without retrieval log (historical or sandbox record)
        record = QueryAnalyticsRecord(
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            query_text="Historical query without retrieval log",
            outcome="SUCCESS",
            total_duration_ms=200.0,
            confidence_score=0.85,
            reliability_score=0.85,
            retry_attempts=0,
            is_safe_to_serve=True,
            created_at=datetime.now(UTC),
        )
        session.add(record)
        await session.commit()

        repo = AnalyticsRepository(session)
        service = QueryAnalyticsService(repo)

        trace_detail = await service.get_query_trace_detail(
            correlation_id=correlation_id, tenant_id=tenant_id
        )

        assert trace_detail.is_authoritative is False
        for stage in trace_detail.stage_traces:
            assert stage.is_authoritative is False
            assert stage.metadata.get("estimated") is True


@pytest.mark.asyncio
async def test_execute_query_sandbox_canonical_score_persistence():
    """Verify execute_query_sandbox persists reliability_score in canonical 0.0-1.0 float scale."""
    tenant_id = f"test-tenant-{uuid.uuid4()}"

    async with get_session_factory()() as session:
        repo = AnalyticsRepository(session)
        service = QueryAnalyticsService(repo)

        req = QuerySandboxRequestDTO(
            query_text="Testing sandbox canonical score normalization",
            retrieval_strategy="hybrid",
            top_k=5,
            confidence_threshold=0.75,
            enable_reranking=True,
            enable_self_correction=True,
        )

        resp = await service.execute_query_sandbox(req, tenant_id=tenant_id)
        assert resp.outcome == "SUCCESS"
        assert resp.correlation_id is not None

        # Verify persisted record in PostgreSQL
        stored_record = await repo.get_record_by_correlation_id(
            correlation_id=resp.correlation_id, tenant_id=tenant_id
        )
        assert stored_record is not None
        assert stored_record.reliability_score is not None
        # Canonical scale: strictly 0.0000 to 1.0000, NOT percentage > 1.0
        assert 0.0 <= stored_record.reliability_score <= 1.0
        assert stored_record.reliability_score == round(stored_record.confidence_score, 4)
