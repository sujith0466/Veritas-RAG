"""Unit Tests for Reliability Module REST API Routes (`ADR-005`, `Phase 2 Milestone 5`).

Tests `POST /api/v1/reliability/search`, `GET /api/v1/reliability/circuit-breakers/{target}`,
`POST /api/v1/reliability/circuit-breakers/{target}/reset`, and `GET /api/v1/reliability/sla-summary`.
"""

from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from backend.main import create_app
from backend.modules.reliability.api.dependencies import (
    get_reliability_gateway,
    get_reliability_repository,
)
from backend.modules.retrieval.api.dependencies import resolve_tenant
from backend.modules.reliability.circuit_breaker.states import CircuitState
from backend.modules.reliability.schemas.errors import CircuitBreakerOpenError
from backend.modules.reliability.schemas.reliability_dto import (
    CircuitBreakerStateDTO,
    ReliableCandidateDTO,
    ReliableRetrievalResultDTO,
    SLASummaryDTO,
)


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


@pytest.fixture
def mock_gateway() -> MagicMock:
    gateway = MagicMock()
    gateway.execute_reliable_search = AsyncMock(
        return_value=ReliableRetrievalResultDTO(
            query_text="reliability test",
            tenant_id="tenant_test",
            correlation_id="corr_api",
            candidates=[
                ReliableCandidateDTO(
                    chunk_id="chunk_api_1",
                    document_id="doc_api_1",
                    document_version_id="ver_api_1",
                    tenant_id="tenant_test",
                    content="Reliable search result content",
                    score=0.95,
                    rank=1,
                )
            ],
            duration_ms=150.0,
            is_sla_breached=False,
            is_degraded_fallback=False,
        )
    )
    gateway.get_circuit_breaker_state = AsyncMock(
        return_value=CircuitBreakerStateDTO(
            tenant_id="tenant_test",
            target="qdrant_hybrid",
            state=CircuitState.CLOSED,
            failures=0,
            cooldown_ttl_seconds=0,
        )
    )
    gateway.force_reset_circuit_breaker = AsyncMock(return_value=True)
    return gateway


@pytest.fixture
def mock_repository() -> MagicMock:
    repo = MagicMock()
    repo.get_tenant_sla_summary = AsyncMock(
        return_value=SLASummaryDTO(
            tenant_id="tenant_test",
            total_queries=100,
            breached_queries=2,
            degraded_queries=5,
            sla_compliance_rate=98.0,
            p95_latency_ms=280.0,
        )
    )
    return repo


def test_execute_reliable_search_200(app: FastAPI, client: TestClient, mock_gateway: MagicMock) -> None:
    app.dependency_overrides[resolve_tenant] = lambda: "tenant_test"
    app.dependency_overrides[get_reliability_gateway] = lambda: mock_gateway

    payload = {
        "query": "reliability test",
        "top_k": 5,
        "sla_budget_ms": 400.0,
        "enable_fallback": True,
        "enable_zero_result_recovery": True,
    }
    response = client.post("/api/v1/reliability/search", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["query_text"] == "reliability test"
    assert data["tenant_id"] == "tenant_test"
    assert len(data["candidates"]) == 1
    assert data["candidates"][0]["content"] == "Reliable search result content"
    mock_gateway.execute_reliable_search.assert_called_once()
    app.dependency_overrides.clear()


def test_execute_reliable_search_empty_query_400(app: FastAPI, client: TestClient, mock_gateway: MagicMock) -> None:
    app.dependency_overrides[resolve_tenant] = lambda: "tenant_test"
    app.dependency_overrides[get_reliability_gateway] = lambda: mock_gateway

    payload = {"query": "   ", "top_k": 5}
    response = client.post("/api/v1/reliability/search", json=payload)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "RET_001"
    app.dependency_overrides.clear()


def test_execute_reliable_search_circuit_open_raises_rel_001(
    app: FastAPI, client: TestClient, mock_gateway: MagicMock
) -> None:
    mock_gateway.execute_reliable_search.side_effect = CircuitBreakerOpenError(
        tenant_id="tenant_test", target="qdrant_hybrid"
    )
    app.dependency_overrides[resolve_tenant] = lambda: "tenant_test"
    app.dependency_overrides[get_reliability_gateway] = lambda: mock_gateway

    payload = {"query": "test query", "top_k": 5}
    response = client.post("/api/v1/reliability/search", json=payload)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "REL_001"
    app.dependency_overrides.clear()


def test_get_circuit_breaker_state_200(app: FastAPI, client: TestClient, mock_gateway: MagicMock) -> None:
    app.dependency_overrides[resolve_tenant] = lambda: "tenant_test"
    app.dependency_overrides[get_reliability_gateway] = lambda: mock_gateway

    response = client.get("/api/v1/reliability/circuit-breakers/qdrant_hybrid")

    assert response.status_code == 200
    data = response.json()
    assert data["tenant_id"] == "tenant_test"
    assert data["target"] == "qdrant_hybrid"
    assert data["state"] == "CLOSED"
    mock_gateway.get_circuit_breaker_state.assert_called_once_with(tenant_id="tenant_test", target="qdrant_hybrid")
    app.dependency_overrides.clear()


def test_force_reset_circuit_breaker_200(app: FastAPI, client: TestClient, mock_gateway: MagicMock) -> None:
    app.dependency_overrides[resolve_tenant] = lambda: "tenant_test"
    app.dependency_overrides[get_reliability_gateway] = lambda: mock_gateway

    response = client.post(
        "/api/v1/reliability/circuit-breakers/qdrant_hybrid/reset"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["state"] == "CLOSED"
    mock_gateway.force_reset_circuit_breaker.assert_called_once_with(tenant_id="tenant_test", target="qdrant_hybrid")
    app.dependency_overrides.clear()


def test_get_sla_summary_200(app: FastAPI, client: TestClient, mock_repository: MagicMock) -> None:
    app.dependency_overrides[resolve_tenant] = lambda: "tenant_test"
    app.dependency_overrides[get_reliability_repository] = lambda: mock_repository

    response = client.get("/api/v1/reliability/sla-summary")

    assert response.status_code == 200
    data = response.json()
    assert data["tenant_id"] == "tenant_test"
    assert data["sla_compliance_rate"] == 98.0
    assert data["p95_latency_ms"] == 280.0
    mock_repository.get_tenant_sla_summary.assert_called_once_with("tenant_test")
    app.dependency_overrides.clear()
