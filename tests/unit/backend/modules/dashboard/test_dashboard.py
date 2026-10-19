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

    # Mocking execute calls sequentially: chunk count/avg, strategy group, embedding count/model, token consumption, health scans, doc metrics, meta, job duration
    mock_chunk_res = MagicMock()
    mock_chunk_res.first.return_value = (45, 128.5)

    mock_strat_res = MagicMock()
    mock_strat_res.all.return_value = [("semantic", 30), ("hierarchical", 15)]

    mock_emb_res = MagicMock()
    mock_emb_res.all.return_value = [("openai", "text-embedding-3-large", 1536, 45)]

    mock_token_res = MagicMock()
    mock_token_res.scalar_one_or_none.return_value = 5782

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
    mock_doc_res.first.return_value = (5, 5, 0, 0)

    mock_meta_res = MagicMock()
    mock_meta_res.scalars.return_value.all.return_value = ["raguard_knowledge_tenant_1"]

    mock_job_res = MagicMock()
    mock_job_res.scalar_one_or_none.return_value = 145.0

    mock_session.execute = AsyncMock(side_effect=[
        mock_chunk_res,
        mock_strat_res,
        mock_emb_res,
        mock_token_res,
        mock_scan_res,
        mock_doc_res,
        mock_meta_res,
        mock_job_res,
    ])

    from unittest.mock import patch
    with patch("backend.modules.vector.providers.factory.VectorProviderFactory.get_provider") as mock_get_provider:
        mock_provider = AsyncMock()
        mock_col_info = MagicMock(points_count=45, vector_dimension=1536, status="green")
        mock_provider.get_collection_info.return_value = mock_col_info
        mock_get_provider.return_value = mock_provider

        service = DashboardService(session=mock_session)
        summary = await service.get_knowledge_intelligence_summary("tenant_1")

        assert summary.tenant_id == "tenant_1"
        assert summary.total_chunks == 45
        assert summary.avg_tokens_per_chunk == 128.5
        assert summary.chunk_strategy_counts == {"semantic": 30, "hierarchical": 15}
        assert summary.total_embeddings == 45
        assert summary.active_embedding_provider == "openai"
        assert "PARITY_CONFIRMED" in summary.parity_audit_status
        assert len(summary.recent_health_scans) == 1
        assert len(summary.stage_latencies) == 4
        assert mock_session.execute.call_count == 8


@pytest.mark.asyncio
async def test_get_executive_dashboard() -> None:
    mock_session = MagicMock()

    # Mocking execute calls sequentially: total/averages, outcomes, recent activity
    mock_stats_res = MagicMock()
    mock_stats_res.first.return_value = (100, 0.89, 96.2, 145.0)

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
