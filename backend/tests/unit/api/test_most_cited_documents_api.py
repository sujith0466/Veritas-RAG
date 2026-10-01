import datetime
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import pytest
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.permissions.rbac import Role
from backend.modules.analytics.api.routes import router
from backend.modules.analytics.schemas.analytics_dto import MostCitedDocumentDTO
from backend.modules.analytics.repositories.analytics_repository import AnalyticsRepository


@pytest.fixture
def analytics_test_app():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/analytics")
    return app


@pytest.mark.asyncio
async def test_get_most_cited_documents_endpoint_success(analytics_test_app):
    ws_id = uuid.uuid4()
    doc_id = str(uuid.uuid4())
    user = UserContext(
        id=uuid.uuid4(),
        email="viewer@test.com",
        role=Role.VIEWER.value,
        workspace_id=ws_id,
        tenant_id=str(ws_id),
    )
    analytics_test_app.dependency_overrides[get_current_user] = lambda: user

    expected_docs = [
        MostCitedDocumentDTO(
            document_id=doc_id,
            document_title="Security_Guidelines.pdf",
            citation_count=12,
            last_cited_at=datetime.datetime(2026, 9, 29, 12, 0, 0, tzinfo=datetime.timezone.utc),
        )
    ]

    with patch(
        "backend.modules.analytics.services.analytics_service.QueryAnalyticsService.get_most_cited_documents",
        new_callable=AsyncMock,
    ) as mock_service:
        mock_service.return_value = [d.model_dump() for d in expected_docs]

        transport = ASGITransport(app=analytics_test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get("/api/v1/analytics/most-cited-documents")
            assert res.status_code == 200
            json_res = res.json()
            assert json_res["success"] is True
            assert len(json_res["data"]) == 1
            item = json_res["data"][0]
            assert item["document_id"] == doc_id
            assert item["document_title"] == "Security_Guidelines.pdf"
            assert item["citation_count"] == 12

            # Verify tenant isolation passed to service filter
            call_filter = mock_service.call_args[0][0]
            assert call_filter.tenant_id == str(ws_id)


@pytest.mark.asyncio
async def test_get_most_cited_documents_empty_state(analytics_test_app):
    ws_id = uuid.uuid4()
    user = UserContext(
        id=uuid.uuid4(),
        email="admin@test.com",
        role=Role.ADMIN.value,
        workspace_id=ws_id,
        tenant_id=str(ws_id),
    )
    analytics_test_app.dependency_overrides[get_current_user] = lambda: user

    with patch(
        "backend.modules.analytics.services.analytics_service.QueryAnalyticsService.get_most_cited_documents",
        new_callable=AsyncMock,
    ) as mock_service:
        mock_service.return_value = []

        transport = ASGITransport(app=analytics_test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get("/api/v1/analytics/most-cited-documents")
            assert res.status_code == 200
            json_res = res.json()
            assert json_res["success"] is True
            assert json_res["data"] == []


@pytest.mark.asyncio
async def test_get_most_cited_documents_workspace_isolation(analytics_test_app):
    ws_a = uuid.uuid4()
    ws_b = uuid.uuid4()

    user_a = UserContext(id=uuid.uuid4(), email="user_a@test.com", role=Role.ADMIN.value, workspace_id=ws_a, tenant_id=str(ws_a))
    analytics_test_app.dependency_overrides[get_current_user] = lambda: user_a

    with patch(
        "backend.modules.analytics.services.analytics_service.QueryAnalyticsService.get_most_cited_documents",
        new_callable=AsyncMock,
    ) as mock_service:
        mock_service.return_value = []
        transport = ASGITransport(app=analytics_test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.get("/api/v1/analytics/most-cited-documents")
            call_filter_a = mock_service.call_args[0][0]
            assert call_filter_a.tenant_id == str(ws_a)
            assert call_filter_a.tenant_id != str(ws_b)


@pytest.mark.asyncio
async def test_repository_handles_json_null_and_scalar_citations():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    # Simulate DB rows returning successfully with documents joined
    mock_result.mappings.return_value.all.return_value = [
        {
            "document_id": "dc91927f-cc48-4fd8-a6bd-99c4f44d98f1",
            "document_title": "large_document_test.txt",
            "citation_count": 13,
            "last_cited_at": datetime.datetime(2026, 9, 29, 10, 44, 48, tzinfo=datetime.timezone.utc),
        }
    ]
    mock_session.execute.return_value = mock_result

    repo = AnalyticsRepository(mock_session)
    res = await repo.get_most_cited_documents("63e0de56-cb8a-45dd-a417-688f0c88ffbb")

    assert len(res) == 1
    assert res[0]["document_title"] == "large_document_test.txt"
    assert res[0]["citation_count"] == 13

    # Assert executed query uses lateral json_array_elements with safe CASE guard
    executed_sql = str(mock_session.execute.call_args[0][0])
    assert "json_typeof(m.citations) = 'array'" in executed_sql
    assert "json_array_elements" in executed_sql
    assert "LEFT JOIN documents d ON elem->>'document_id' = d.id::text AND d.tenant_id = :tenant_id" in executed_sql
