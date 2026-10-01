"""Unit and integration tests for DASH-001: Dashboard correctness, time-window consistency, and truthful empty states."""

from datetime import UTC, datetime, timedelta
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.engine import get_async_session
from backend.modules.analytics.models.query_analytics import QueryAnalyticsRecord
from backend.modules.dashboard.schemas.dashboard_dto import ExecutiveDashboardDTO
from backend.modules.dashboard.services.dashboard_service import DashboardService


@pytest.mark.asyncio
async def test_dashboard_empty_window_truthful_semantics():
    """Verify that when 0 queries exist in the selected window, averages are None rather than misleading 0.0%."""
    async for session in get_async_session():
        svc = DashboardService(session)
        # Using a tenant ID that has no queries in the last 1h
        test_tenant = "63e0de56-cb8a-45dd-a417-688f0c88ffbb"

        res: ExecutiveDashboardDTO = await svc.get_executive_dashboard(test_tenant, time_window="1h")
        assert res.time_window == "1h"
        assert res.total_queries == 0
        assert res.avg_reliability_score is None
        assert res.avg_confidence_score is None
        assert res.avg_latency_ms is None
        assert len(res.recent_activity) == 0
        assert res.active_tenants >= 1
        assert res.system_status in ("OPERATIONAL", "DEGRADED", "OUTAGE")
        break


@pytest.mark.asyncio
async def test_dashboard_populated_window_metrics():
    """Verify that when queries exist in the selected window (e.g. 'all'), metrics reflect actual averages."""
    async for session in get_async_session():
        svc = DashboardService(session)
        test_tenant = "63e0de56-cb8a-45dd-a417-688f0c88ffbb"

        res: ExecutiveDashboardDTO = await svc.get_executive_dashboard(test_tenant, time_window="all")
        assert res.time_window == "all"
        assert res.total_queries > 0
        assert res.avg_reliability_score is not None
        assert res.avg_confidence_score is not None
        assert len(res.recent_activity) > 0
        # Check backward compatibility field
        assert isinstance(res.total_queries_last_24h, int)
        break


@pytest.mark.asyncio
async def test_dashboard_window_parameter_handling():
    """Verify that invalid time windows default safely to 24h."""
    async for session in get_async_session():
        svc = DashboardService(session)
        test_tenant = "63e0de56-cb8a-45dd-a417-688f0c88ffbb"

        res = await svc.get_executive_dashboard(test_tenant, time_window="invalid_window")
        assert res.time_window == "24h"
        break


@pytest.mark.asyncio
async def test_knowledge_intelligence_summary_truthful_parity_and_metrics():
    """Verify knowledge intelligence summary computes truthful metrics, honest pass rate, and real Qdrant parity."""
    async for session in get_async_session():
        svc = DashboardService(session)
        test_tenant = "63e0de56-cb8a-45dd-a417-688f0c88ffbb"

        summary = await svc.get_knowledge_intelligence_summary(test_tenant)
        assert summary.tenant_id == test_tenant
        assert summary.total_documents >= 0
        assert summary.processed_documents >= 0
        assert summary.pending_documents >= 0
        assert summary.failed_documents >= 0
        assert 0.0 <= summary.validation_pass_rate <= 100.0
        assert summary.total_chunks >= 0
        assert summary.total_embeddings >= 0
        assert summary.total_embedding_tokens_consumed >= 0

        # Stage latencies SLA transparency
        assert len(summary.stage_latencies) == 4
        for stage in summary.stage_latencies:
            assert stage.is_measured is False

        # Parity status must be honest and include exact counts
        if summary.total_chunks == summary.total_vector_points:
            assert summary.parity_audit_status.startswith("PARITY_CONFIRMED")
        else:
            assert summary.parity_audit_status.startswith("MISMATCH_DETECTED")
            assert str(summary.total_chunks) in summary.parity_audit_status
            assert str(summary.total_vector_points) in summary.parity_audit_status

        assert summary.vector_cluster_status in ("green", "yellow", "red")
        break


@pytest.mark.asyncio
async def test_knowledge_intelligence_empty_tenant_truthful_defaults():
    """Verify knowledge intelligence summary produces correct baseline defaults for a tenant with 0 records."""
    async for session in get_async_session():
        svc = DashboardService(session)
        empty_tenant = "00000000-0000-0000-0000-000000000000"

        summary = await svc.get_knowledge_intelligence_summary(empty_tenant)
        assert summary.tenant_id == empty_tenant
        assert summary.total_documents == 0
        assert summary.processed_documents == 0
        assert summary.pending_documents == 0
        assert summary.failed_documents == 0
        assert summary.validation_pass_rate == 100.0
        assert summary.total_chunks == 0
        assert summary.avg_tokens_per_chunk == 0.0
        assert summary.chunk_strategy_counts == {}
        assert summary.total_embeddings == 0
        assert summary.total_embedding_tokens_consumed == 0
        assert summary.total_vector_points == 0
        assert summary.parity_audit_status == "PARITY_CONFIRMED (0 == 0)"
        break
