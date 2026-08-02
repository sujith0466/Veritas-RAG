"""Unit tests for Dashboard & Knowledge Intelligence (`Phase 4 Milestone 3`)."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from backend.modules.analytics.models.query_analytics import QueryAnalyticsRecord
from backend.modules.dashboard.services.dashboard_service import DashboardService
from backend.modules.knowledge_health.models.health_scan import HealthScanJob


@pytest.mark.asyncio
async def test_get_knowledge_intelligence_summary() -> None:
    mock_session = MagicMock()

    # Mocking execute calls sequentially: chunk count/avg, strategy group, embedding count/model, health scans
    mock_chunk_res = MagicMock()
    mock_chunk_res.first.return_value = (45, 128.5)

    mock_strat_res = MagicMock()
    mock_strat_res.all.return_value = [("semantic", 30), ("hierarchical", 15)]

    mock_emb_res = MagicMock()
    mock_emb_res.first.return_value = (45, "openai", "text-embedding-3-large")

    mock_scan_res = MagicMock()
    mock_scan = HealthScanJob(
        id=uuid4(),
        tenant_id="tenant_1",
        scan_type="PARITY_AUDIT",
        status="COMPLETED",
        orphans_found=0,
        orphans_purged=0,
        parity_status="CONFIRMED",
    )
    mock_scan_res.scalars.return_value.all.return_value = [mock_scan]

    mock_doc_res = MagicMock()
    mock_doc_res.first.return_value = (5, 5, 0)

    mock_session.execute = AsyncMock(side_effect=[
        mock_chunk_res,
        mock_strat_res,
        mock_emb_res,
        mock_scan_res,
        mock_doc_res,
    ])

    service = DashboardService(session=mock_session)
    summary = await service.get_knowledge_intelligence_summary("tenant_1")

    assert summary.tenant_id == "tenant_1"
    assert summary.total_chunks == 45
    assert summary.avg_tokens_per_chunk == 128.5
    assert summary.chunk_strategy_counts == {"semantic": 30, "hierarchical": 15}
    assert summary.total_embeddings == 45
    assert summary.active_embedding_provider == "openai"
    assert summary.parity_audit_status == "PARITY_CONFIRMED"
    assert len(summary.recent_health_scans) == 1
    assert len(summary.stage_latencies) == 4
    assert mock_session.execute.call_count == 5


@pytest.mark.asyncio
async def test_get_executive_dashboard() -> None:
    mock_session = MagicMock()

    # Mocking execute calls sequentially: total/averages, outcomes, recent activity
    mock_stats_res = MagicMock()
    mock_stats_res.first.return_value = (100, 0.89, 96.2)

    mock_outcomes_res = MagicMock()
    mock_outcomes_res.all.return_value = [
        ("SUCCESS", 90),
        ("ABORTED_HALLUCINATION", 5),
        ("CLARIFICATION_REQUIRED", 5),
    ]

    mock_rec1 = QueryAnalyticsRecord(
        id=uuid4(),
        tenant_id="tenant_1",
        correlation_id="corr_1",
        query_text="Secret docs check",
        outcome="ABORTED_HALLUCINATION",
        total_duration_ms=45.0,
        confidence_score=0.42,
        reliability_score=40.0,
        retry_attempts=1,
    )
    mock_rec1.created_at = datetime.now(UTC)

    mock_activity_res = MagicMock()
    mock_activity_res.scalars.return_value.all.return_value = [mock_rec1]

    mock_session.execute = AsyncMock(side_effect=[
        mock_stats_res,
        mock_outcomes_res,
        mock_activity_res,
    ])

    service = DashboardService(session=mock_session)
    dashboard = await service.get_executive_dashboard("tenant_1")

    assert dashboard.tenant_id == "tenant_1"
    assert dashboard.total_queries_last_24h == 100
    assert dashboard.avg_reliability_score == 96.2
    assert dashboard.avg_confidence_score == 0.89
    assert dashboard.blocked_hallucinations_last_24h == 5
    assert dashboard.clarification_rate == 5.0
    assert len(dashboard.recent_activity) == 1
    assert len(dashboard.security_alerts) == 1
    assert dashboard.security_alerts[0].alert_type == "HALLUCINATION_PREVENTION"
