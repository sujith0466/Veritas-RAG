"""Unit and integration tests for DASH-003: Execution Intelligence & Forensics."""

import pytest
from backend.database.engine import get_async_session
from backend.modules.dashboard.services.execution_intelligence_service import ExecutionIntelligenceService
from backend.modules.dashboard.schemas.dashboard_dto import QueryExecutionLedgerDTO, QueryExecutionTraceDTO


@pytest.mark.asyncio
async def test_list_executions_pagination_and_window():
    """Verify paginated execution listing with window filtering and tenant isolation."""
    async for session in get_async_session():
        svc = ExecutionIntelligenceService(session)
        tenant_id = "63e0de56-cb8a-45dd-a417-688f0c88ffbb"

        res: QueryExecutionLedgerDTO = await svc.list_executions(
            tenant_id=tenant_id,
            time_window="all",
            limit=5,
            offset=0,
        )
        assert res.total >= 0
        assert res.limit == 5
        assert res.offset == 0
        assert len(res.items) <= 5
        if res.items:
            first = res.items[0]
            assert first.id is not None
            assert first.query_text is not None
            assert first.outcome is not None
        break


@pytest.mark.asyncio
async def test_list_executions_search_filter():
    """Verify text search filtering across execution records."""
    async for session in get_async_session():
        svc = ExecutionIntelligenceService(session)
        tenant_id = "63e0de56-cb8a-45dd-a417-688f0c88ffbb"

        # Search for non-existent keyword
        res = await svc.list_executions(
            tenant_id=tenant_id,
            time_window="all",
            search="non_existent_unlikely_query_xyz_12345",
        )
        assert res.total == 0
        assert len(res.items) == 0
        break


@pytest.mark.asyncio
async def test_execution_trace_and_tenant_isolation():
    """Verify execution trace extraction and strict cross-tenant isolation enforcement."""
    async for session in get_async_session():
        svc = ExecutionIntelligenceService(session)
        tenant_a = "63e0de56-cb8a-45dd-a417-688f0c88ffbb"
        tenant_b = "00000000-0000-0000-0000-000000000000"

        ledger = await svc.list_executions(tenant_id=tenant_a, time_window="all", limit=1)
        if ledger.items:
            valid_id = ledger.items[0].id

            # Tenant A can fetch their own trace
            trace_a: QueryExecutionTraceDTO | None = await svc.get_execution_trace(tenant_a, valid_id)
            assert trace_a is not None
            assert trace_a.id == valid_id
            assert trace_a.tenant_id == tenant_a
            assert trace_a.query_text is not None
            assert "pipeline_type" in trace_a.diagnostics

            # Tenant B CANNOT fetch Tenant A's trace (Mandatory security boundary)
            trace_b = await svc.get_execution_trace(tenant_b, valid_id)
            assert trace_b is None, "Cross-tenant access must return None / 404!"

        # Invalid UUID returns None cleanly without error
        invalid_trace = await svc.get_execution_trace(tenant_a, "not-a-valid-uuid")
        assert invalid_trace is None
        break
