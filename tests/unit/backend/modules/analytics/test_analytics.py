"""Unit tests for Query Analytics & Reliability Intelligence (`Phase 4 Milestone 1`)."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from backend.modules.analytics.models.query_analytics import QueryAnalyticsRecord
from backend.modules.analytics.repositories.analytics_repository import AnalyticsRepository
from backend.modules.analytics.schemas.analytics_dto import AnalyticsFilterDTO
from backend.modules.analytics.schemas.errors import InvalidDateRange
from backend.modules.analytics.services.analytics_service import QueryAnalyticsService


@pytest.mark.asyncio
async def test_record_query_execution() -> None:
    mock_session = MagicMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    repo = AnalyticsRepository(session=mock_session)
    service = QueryAnalyticsService(repository=repo)

    rec_id = await service.record_query_execution(
        tenant_id="tenant_1",
        correlation_id="corr_abc",
        query_text="What is the security SLA?",
        outcome="SUCCESS",
        total_duration_ms=120.5,
        confidence_score=0.88,
        hallucination_score=0.05,
        reliability_score=92.0,
        retry_attempts=0,
        is_safe_to_serve=True,
    )
    assert rec_id is not None
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_get_success_rate() -> None:
    mock_session = MagicMock()
    # Mock records returned by session.scalars(query).all()
    rec1 = QueryAnalyticsRecord(
        tenant_id="tenant_1",
        correlation_id="corr_1",
        query_text="q1",
        outcome="SUCCESS",
        total_duration_ms=100.0,
        confidence_score=0.9,
        reliability_score=95.0,
        retry_attempts=0,
    )
    rec2 = QueryAnalyticsRecord(
        tenant_id="tenant_1",
        correlation_id="corr_2",
        query_text="q2",
        outcome="CLARIFICATION_REQUIRED",
        total_duration_ms=80.0,
        confidence_score=0.4,
        reliability_score=50.0,
        retry_attempts=1,
    )
    rec3 = QueryAnalyticsRecord(
        tenant_id="tenant_1",
        correlation_id="corr_3",
        query_text="q3",
        outcome="ABORTED_HALLUCINATION",
        total_duration_ms=150.0,
        confidence_score=0.8,
        reliability_score=30.0,
        retry_attempts=2,
    )

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [rec1, rec2, rec3]
    mock_session.scalars = AsyncMock(return_value=mock_scalars)

    repo = AnalyticsRepository(session=mock_session)
    service = QueryAnalyticsService(repository=repo)

    dto = await service.get_success_rate(AnalyticsFilterDTO(tenant_id="tenant_1"))
    assert dto.total_queries == 3
    assert dto.success_count == 1
    assert dto.clarification_count == 1
    assert dto.failure_count == 1
    assert dto.retry_count == 2
    assert dto.success_rate_percentage == round((1 / 3) * 100, 2)
    assert dto.avg_retries_per_query == round(3 / 3, 2)


@pytest.mark.asyncio
async def test_get_latency_analytics() -> None:
    mock_session = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [50.0, 100.0, 150.0, 200.0, 250.0]
    mock_session.scalars = AsyncMock(return_value=mock_scalars)

    repo = AnalyticsRepository(session=mock_session)
    service = QueryAnalyticsService(repository=repo)

    latency = await service.get_latency_analytics(AnalyticsFilterDTO(tenant_id="tenant_1"))
    assert latency.avg_ms == 150.0
    assert latency.p50_ms == 150.0
    assert latency.p90_ms == 250.0


@pytest.mark.asyncio
async def test_get_confidence_analytics() -> None:
    mock_session = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [0.85, 0.90, 0.60, 0.35]
    mock_session.scalars = AsyncMock(return_value=mock_scalars)

    repo = AnalyticsRepository(session=mock_session)
    service = QueryAnalyticsService(repository=repo)

    conf = await service.get_confidence_analytics(AnalyticsFilterDTO(tenant_id="tenant_1"))
    assert conf.high_confidence_count == 2
    assert conf.medium_confidence_count == 1
    assert conf.low_confidence_count == 1
    assert conf.max_confidence == 0.90
    assert conf.min_confidence == 0.35


@pytest.mark.asyncio
async def test_invalid_date_range_raises_exception() -> None:
    mock_session = MagicMock()
    repo = AnalyticsRepository(session=mock_session)
    service = QueryAnalyticsService(repository=repo)

    with pytest.raises(InvalidDateRange):
        await service.get_success_rate(
            AnalyticsFilterDTO(
                tenant_id="tenant_1",
                start_time=datetime(2026, 7, 20, tzinfo=timezone.utc),
                end_time=datetime(2026, 7, 10, tzinfo=timezone.utc),
            )
        )


@pytest.mark.asyncio
async def test_get_query_trace_detail() -> None:
    mock_session = MagicMock()
    mock_record = QueryAnalyticsRecord(
        tenant_id="tenant_1",
        correlation_id="corr_trace_123",
        query_text="What is the data retention period?",
        outcome="SUCCESS",
        total_duration_ms=210.0,
        confidence_score=0.91,
        reliability_score=94.5,
        retry_attempts=0,
        is_safe_to_serve=True,
    )
    mock_record.id = uuid4()
    mock_record.created_at = datetime.now(timezone.utc)
    mock_session.scalar = AsyncMock(return_value=mock_record)

    repo = AnalyticsRepository(session=mock_session)
    service = QueryAnalyticsService(repository=repo)

    trace = await service.get_query_trace_detail(correlation_id="corr_trace_123", tenant_id="tenant_1")
    assert trace.record.correlation_id == "corr_trace_123"
    assert len(trace.stage_traces) == 5
    assert len(trace.retrieval_candidates) == 2
    assert len(trace.confidence_signals) == 3


@pytest.mark.asyncio
async def test_execute_query_sandbox() -> None:
    mock_session = MagicMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    mock_record = QueryAnalyticsRecord(
        tenant_id="tenant_1",
        correlation_id="sandbox_trace_abc",
        query_text="What is the uptime SLA?",
        outcome="SUCCESS",
        total_duration_ms=200.0,
        confidence_score=0.88,
        reliability_score=88.0,
        retry_attempts=0,
        is_safe_to_serve=True,
    )
    mock_record.id = uuid4()
    mock_record.created_at = datetime.now(timezone.utc)
    mock_session.scalar = AsyncMock(return_value=mock_record)

    repo = AnalyticsRepository(session=mock_session)
    service = QueryAnalyticsService(repository=repo)

    from backend.modules.analytics.schemas.analytics_dto import QuerySandboxRequestDTO
    request_dto = QuerySandboxRequestDTO(
        query_text="What is the uptime SLA?",
        retrieval_strategy="hybrid",
        top_k=5,
        confidence_threshold=0.75,
        enable_reranking=True,
        enable_self_correction=True,
    )

    res = await service.execute_query_sandbox(request_dto=request_dto, tenant_id="tenant_1")
    assert res.correlation_id is not None
    assert res.outcome in ("SUCCESS", "CLARIFICATION_REQUIRED", "ABORTED_LOW_CONFIDENCE")
    assert res.trace_detail is not None
