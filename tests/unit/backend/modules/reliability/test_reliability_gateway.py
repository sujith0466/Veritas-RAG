"""Unit Tests for ReliabilityGateway (`ADR-005`, `Phase 2 Milestone 5`).

Tests SLA compliance checks ($400\text{ms}$ budget), fast failover when circuit is OPEN,
degraded fallback execution on primary timeouts (`asyncio.TimeoutError`), and zero-result recovery.
"""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock
import uuid
import pytest
from backend.modules.reliability.circuit_breaker.engine import CircuitBreakerEngine
from backend.modules.reliability.circuit_breaker.states import CircuitState
from backend.modules.reliability.fallbacks.router import FallbackRouter
from backend.modules.reliability.fallbacks.zero_result import ZeroResultRecoverer
from backend.modules.reliability.repositories.reliability_repository import ReliabilityRepository
from backend.modules.reliability.schemas.errors import CircuitBreakerOpenError
from backend.modules.reliability.schemas.reliability_dto import (
    ReliableCandidateDTO,
    ReliableRetrievalResultDTO,
    SearchOptionsDTO,
)
from backend.modules.reliability.services.reliability_gateway import ReliabilityGateway
from backend.modules.retrieval.schemas.retrieval_dto import (
    RankedEvidenceDTO,
    RetrievalResultDTO,
    RetrievalStageBreakdownDTO,
)
from backend.modules.retrieval.services.retrieval_service import RetrievalOrchestrator


@pytest.fixture
def mock_orchestrator() -> AsyncMock:
    return AsyncMock(spec=RetrievalOrchestrator)


@pytest.fixture
def mock_circuit_breaker() -> AsyncMock:
    cb = AsyncMock(spec=CircuitBreakerEngine)
    cb.check_state.return_value = CircuitState.CLOSED
    cb.failure_threshold = 5
    return cb


@pytest.fixture
def mock_fallback_router() -> AsyncMock:
    fr = AsyncMock(spec=FallbackRouter)
    fr.route_fallback.return_value = ReliableRetrievalResultDTO(
        query_text="test",
        tenant_id="tenant_1",
        correlation_id="corr_fallback",
        candidates=[
            ReliableCandidateDTO(
                chunk_id="fb_1",
                document_id="doc_fb",
                document_version_id="ver_fb",
                tenant_id="tenant_1",
                content="Fallback BM25 content",
                score=10.0,
                rank=1,
                source="fallback_bm25",
                is_fallback=True,
            )
        ],
        duration_ms=45.0,
        is_degraded_fallback=True,
        fallback_reason="CircuitBreakerOpen",
    )
    return fr


@pytest.fixture
def mock_zero_recoverer() -> AsyncMock:
    zr = AsyncMock(spec=ZeroResultRecoverer)
    zr.recover_empty_results.return_value = ReliableRetrievalResultDTO(
        query_text="test",
        tenant_id="tenant_1",
        correlation_id="corr_zr",
        candidates=[
            ReliableCandidateDTO(
                chunk_id="zr_1",
                document_id="doc_zr",
                document_version_id="ver_zr",
                tenant_id="tenant_1",
                content="Broadened content",
                score=7.0,
                rank=1,
                source="zero_broadened",
                is_broadened=True,
            )
        ],
        duration_ms=30.0,
        is_zero_result_broadened=True,
    )
    return zr


@pytest.fixture
def gateway(
    mock_orchestrator: AsyncMock,
    mock_circuit_breaker: AsyncMock,
    mock_fallback_router: AsyncMock,
    mock_zero_recoverer: AsyncMock,
) -> ReliabilityGateway:
    return ReliabilityGateway(
        orchestrator=mock_orchestrator,
        circuit_breaker=mock_circuit_breaker,
        fallback_router=mock_fallback_router,
        zero_result_recoverer=mock_zero_recoverer,
        target_module="qdrant_hybrid",
    )


@pytest.mark.asyncio
async def test_normal_path_clean_retrieval(
    gateway: ReliabilityGateway, mock_orchestrator: AsyncMock, mock_circuit_breaker: AsyncMock
) -> None:
    chunk_uuid = uuid.UUID("11111111-1111-1111-1111-111111111111")
    doc_uuid = uuid.UUID("22222222-2222-2222-2222-222222222222")
    ver_uuid = uuid.UUID("33333333-3333-3333-3333-333333333333")

    mock_orchestrator.execute_hybrid_search.return_value = RetrievalResultDTO(
        query_text="what is RAG?",
        tenant_id="tenant_1",
        correlation_id="corr_clean",
        top_k_requested=5,
        dense_candidates_count=1,
        sparse_candidates_count=1,
        unique_candidates_merged=1,
        final_evidence=[
            RankedEvidenceDTO(
                chunk_id=chunk_uuid,
                document_id=doc_uuid,
                document_version_id=ver_uuid,
                tenant_id="tenant_1",
                content="RAG is Retrieval-Augmented Generation.",
                rrf_score=0.92,
                final_rank=1,
            )
        ],
        stage_latencies=RetrievalStageBreakdownDTO(total_ms=185.0),
    )

    options = SearchOptionsDTO(top_k=5, sla_budget_ms=400.0)
    result = await gateway.execute_reliable_search(
        query="what is RAG?", tenant_id="tenant_1", options=options, correlation_id="corr_clean"
    )

    assert result.is_degraded_fallback is False
    assert result.is_sla_breached is False
    assert len(result.candidates) == 1
    assert result.candidates[0].chunk_id == str(chunk_uuid)
    mock_circuit_breaker.record_success.assert_called_once_with(tenant_id="tenant_1", target="qdrant_hybrid")


@pytest.mark.asyncio
async def test_circuit_open_fast_failover_to_fallback(
    gateway: ReliabilityGateway, mock_circuit_breaker: AsyncMock, mock_fallback_router: AsyncMock
) -> None:
    mock_circuit_breaker.check_state.return_value = CircuitState.OPEN
    options = SearchOptionsDTO(top_k=5, enable_fallback=True)

    result = await gateway.execute_reliable_search(
        query="test", tenant_id="tenant_1", options=options
    )

    assert result.is_degraded_fallback is True
    assert result.fallback_reason == "CircuitBreakerOpen"
    mock_fallback_router.route_fallback.assert_called_once()


@pytest.mark.asyncio
async def test_circuit_open_fallback_disabled_raises_rel_001(
    gateway: ReliabilityGateway, mock_circuit_breaker: AsyncMock
) -> None:
    mock_circuit_breaker.check_state.return_value = CircuitState.OPEN
    options = SearchOptionsDTO(top_k=5, enable_fallback=False)

    with pytest.raises(CircuitBreakerOpenError) as exc_info:
        await gateway.execute_reliable_search(
            query="test", tenant_id="tenant_1", options=options
        )
    assert exc_info.value.code == "REL_001"


@pytest.mark.asyncio
async def test_primary_timeout_routes_to_fallback(
    gateway: ReliabilityGateway,
    mock_orchestrator: AsyncMock,
    mock_circuit_breaker: AsyncMock,
    mock_fallback_router: AsyncMock,
) -> None:
    async def slow_hybrid(*args: Any, **kwargs: Any) -> Any:
        await asyncio.sleep(0.5)
        return MagicMock()

    mock_orchestrator.execute_hybrid_search.side_effect = slow_hybrid
    mock_circuit_breaker.record_failure.return_value = CircuitState.CLOSED
    options = SearchOptionsDTO(top_k=5, sla_budget_ms=100.0, enable_fallback=True)

    result = await gateway.execute_reliable_search(
        query="test slow query", tenant_id="tenant_1", options=options
    )

    assert result.is_degraded_fallback is True
    assert "Execution timeout" in str(result.fallback_reason)
    mock_circuit_breaker.record_failure.assert_called_once()
    mock_fallback_router.route_fallback.assert_called_once()


@pytest.mark.asyncio
async def test_zero_result_recovery_triggered(
    gateway: ReliabilityGateway,
    mock_orchestrator: AsyncMock,
    mock_zero_recoverer: AsyncMock,
) -> None:
    mock_orchestrator.execute_hybrid_search.return_value = RetrievalResultDTO(
        query_text="empty query",
        tenant_id="tenant_1",
        correlation_id="corr_empty",
        top_k_requested=5,
        dense_candidates_count=0,
        sparse_candidates_count=0,
        unique_candidates_merged=0,
        final_evidence=[],
        stage_latencies=RetrievalStageBreakdownDTO(total_ms=120.0),
    )
    options = SearchOptionsDTO(top_k=5, enable_zero_result_recovery=True)

    result = await gateway.execute_reliable_search(
        query="empty query", tenant_id="tenant_1", options=options
    )

    assert result.is_zero_result_broadened is True
    assert len(result.candidates) == 1
    assert result.candidates[0].source == "zero_broadened"
    mock_zero_recoverer.recover_empty_results.assert_called_once()
