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
