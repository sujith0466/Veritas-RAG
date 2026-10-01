"""Unit and integration tests for DASH-002: Command Center Data Layer."""

import pytest
from backend.database.engine import get_async_session
from backend.modules.dashboard.services.command_center_service import CommandCenterService
from backend.modules.dashboard.schemas.dashboard_dto import CommandCenterDTO


@pytest.mark.asyncio
async def test_command_center_telemetry_aggregation():
    """Verify CommandCenterService returns consolidated telemetry with real metrics."""
    async for session in get_async_session():
        svc = CommandCenterService(session)
        tenant_id = "63e0de56-cb8a-45dd-a417-688f0c88ffbb"

        res: CommandCenterDTO = await svc.get_command_center(tenant_id, time_window="all")
        assert res.tenant_id == tenant_id
        assert res.time_window == "all"
        assert res.system_health.status in ("OPERATIONAL", "DEGRADED", "OUTAGE")
        assert len(res.system_health.components) >= 2
        assert res.kpis.active_tenants >= 1
        assert res.kpis.active_workspaces >= 1
        assert res.kpis.total_queries >= 0
        assert res.knowledge_health.total_documents >= 0
        assert res.knowledge_health.total_chunks >= 0
        assert res.knowledge_health.total_embeddings >= 0
        assert isinstance(res.reliability_trend, list)
        assert isinstance(res.alerts, list)
        break


@pytest.mark.asyncio
async def test_command_center_empty_window():
    """Verify CommandCenterService handles empty time window with semantic correctness."""
    async for session in get_async_session():
        svc = CommandCenterService(session)
        tenant_id = "63e0de56-cb8a-45dd-a417-688f0c88ffbb"

        res: CommandCenterDTO = await svc.get_command_center(tenant_id, time_window="1h")
        assert res.time_window == "1h"
        assert res.kpis.total_queries == 0
        assert res.kpis.avg_reliability_score is None
        assert res.kpis.avg_confidence_score is None
        assert res.kpis.avg_latency_ms is None
        assert res.kpis.p95_latency_ms is None
        assert res.latency_percentiles.p95_ms is None
        assert len(res.reliability_trend) == 0
        break
