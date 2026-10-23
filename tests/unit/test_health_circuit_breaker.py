"""Unit tests for /health/ready probe circuit breaker aggregation (`WP-3C Phase 1`).

Tests:
- 200 OK ('ready') when primary provider circuit breaker is CLOSED (healthy)
- 200 OK ('degraded') when primary provider is OPEN but fallback provider is CLOSED (degraded)
- 503 Service Unavailable ('not_ready') when all configured provider circuit breakers are OPEN
- 503 Service Unavailable when core infrastructure dependency (PostgreSQL/Redis/Qdrant) fails
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

import backend.api.v1.routes.health as health_mod
from backend.api.v1.schemas.common import DependencyHealth
from backend.core.exceptions.handlers import get_exception_handlers
from backend.modules.reliability.circuit_breaker.states import CircuitState


@pytest.fixture(autouse=True)
def clean_startup_state():
    """Ensure startup state is reset before and after each test."""
    health_mod.reset_startup_state()
    yield
    health_mod.reset_startup_state()


@pytest.fixture
def client():
    """Create lightweight test client with health router and exception handlers."""
    test_app = FastAPI()
    for exc_class, handler in get_exception_handlers():
        test_app.add_exception_handler(exc_class, handler)
    test_app.include_router(health_mod.router)
    test_app.include_router(health_mod.router, prefix="/api/v1")
    return TestClient(test_app)


def healthy_infra_deps(llm_status: str = "healthy") -> dict[str, DependencyHealth]:
    return {
        "postgresql": DependencyHealth(name="postgresql", status="healthy"),
        "redis": DependencyHealth(name="redis", status="healthy"),
        "qdrant": DependencyHealth(name="qdrant", status="healthy"),
        "object_storage": DependencyHealth(name="object_storage", status="healthy"),
        "llm_provider": DependencyHealth(
            name="llm_provider",
            status=llm_status,
            info={"provider_status": llm_status},
        ),
    }


def test_readiness_probe_all_providers_healthy(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Readiness probe returns 200 OK and status 'ready' when providers and infra are healthy."""
    async def mock_deps(detailed: bool = False):
        return healthy_infra_deps(llm_status="healthy")

    monkeypatch.setattr(health_mod, "_check_dependencies", mock_deps)

    response = client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["provider_status"] == "healthy"
    assert data["dependencies"]["llm_provider"] == "healthy"


def test_readiness_probe_primary_open_fallback_available_degraded(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Readiness probe returns 200 OK and status 'degraded' when primary is OPEN but fallback is available."""
    async def mock_deps(detailed: bool = False):
        return healthy_infra_deps(llm_status="degraded")

    monkeypatch.setattr(health_mod, "_check_dependencies", mock_deps)

    response = client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["provider_status"] == "degraded"
    assert data["dependencies"]["llm_provider"] == "degraded"


def test_readiness_probe_all_providers_open_unhealthy(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Readiness probe returns 503 Service Unavailable when all configured providers have tripped breakers."""
    async def mock_deps(detailed: bool = False):
        return healthy_infra_deps(llm_status="unhealthy")

    monkeypatch.setattr(health_mod, "_check_dependencies", mock_deps)

    response = client.get("/health/ready")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "not_ready"
    assert data["provider_status"] == "unhealthy"
    assert data["dependencies"]["llm_provider"] == "unhealthy"


def test_readiness_probe_infra_failure_returns_503(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Readiness probe returns 503 if PostgreSQL is unhealthy, even if LLM provider is healthy."""
    async def mock_deps(detailed: bool = False):
        deps = healthy_infra_deps(llm_status="healthy")
        deps["postgresql"] = DependencyHealth(name="postgresql", status="unhealthy")
        return deps

    monkeypatch.setattr(health_mod, "_check_dependencies", mock_deps)

    response = client.get("/health/ready")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "not_ready"
    assert data["dependencies"]["postgresql"] == "unhealthy"


@pytest.mark.asyncio
async def test_check_dependencies_aggregates_circuit_breaker_states(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verifies that _check_dependencies actively queries CircuitBreakerEngine for provider states."""
    from backend.modules.reliability.circuit_breaker.engine import CircuitBreakerEngine

    # Mock settings with primary and fallback providers
    mock_settings = MagicMock()
    mock_settings.ai.priority_list = ["openrouter", "gemini"]

    # Mock circuit breaker states: openrouter OPEN, gemini CLOSED
    async def mock_check_state(self, tenant_id: str, target: str):
        if target == "openrouter":
            return CircuitState.OPEN
        return CircuitState.CLOSED

    monkeypatch.setattr(health_mod, "get_settings", lambda: mock_settings)
    monkeypatch.setattr(CircuitBreakerEngine, "check_state", mock_check_state)

    # Mock infra checks
    monkeypatch.setattr("backend.database.engine.check_db_health", AsyncMock(return_value=True))
    monkeypatch.setattr(
        "backend.cache.client.check_cache_health",
        AsyncMock(return_value={"status": "healthy", "latency_ms": 1.0}),
    )
    monkeypatch.setattr(
        "backend.vector_db.client.check_vector_db_health",
        AsyncMock(return_value={"status": "healthy", "latency_ms": 1.0}),
    )
    monkeypatch.setattr(
        "backend.document.storage.utils.check_storage_health",
        AsyncMock(return_value={"status": "healthy", "latency_ms": 1.0}),
    )

    deps = await health_mod._check_dependencies(detailed=False)
    llm_dep = deps["llm_provider"]

    assert llm_dep.status == "degraded"
    assert llm_dep.info["provider_status"] == "degraded"
    assert llm_dep.info["circuit_states"]["openrouter"] == "OPEN"
    assert llm_dep.info["circuit_states"]["gemini"] == "CLOSED"
