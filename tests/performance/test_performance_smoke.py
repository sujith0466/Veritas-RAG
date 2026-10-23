"""Fast CI Performance Smoke Gate (<30s runtime, T_max <= 500ms).

WP-3D: TSK-3D-04 — Fast CI Performance Smoke Gate.

Adheres strictly to Master Plan Section 7.1(2), 10.2(3), and 12(2):
- Operational latency ceiling: T_max <= 500ms on core REST endpoints across N=20 samples.
- Nominal chat TTFT < 800ms when tested against MockLLMProvider.
- Total suite execution runtime strictly < 30.0s.
- Offline and deterministic: uses MockLLMProvider; zero external API or billing calls.
- Disclaims statistical percentiles for small sample size (N=20).
"""

import asyncio
from datetime import datetime, timezone
import os
import time
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import httpx
import pytest

from backend.ai.interfaces.llm_provider import LLMRequest
from backend.ai.providers.mock_provider import MockLLMProvider
from backend.api.v1.schemas.common import DependencyHealth
from backend.api.v1.schemas.users import UserResponse
from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import (
    get_db,
    get_workspace_member_repository,
    get_workspace_repository,
)
from backend.core.dependencies.user import get_user_profile_service
from backend.core.permissions.rbac import Role
from backend.main import create_app
from backend.models.entities.workspace import Workspace, WorkspaceStatus
from backend.models.entities.workspace_member import WorkspaceMember


@pytest.fixture(scope="module")
def app_instance():
    """Create a FastAPI application instance configured for deterministic offline CI smoke testing."""
    os.environ["ENVIRONMENT"] = "testing"
    os.environ["APP_ENVIRONMENT"] = "testing"
    os.environ["MOCK_LLM_PROVIDER"] = "true"
    os.environ["TRUSTED_PROXIES"] = "127.0.0.1,::1"
    os.environ["OTEL_SDK_DISABLED"] = "true"

    app = create_app()

    qa_user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    qa_tenant_id = "00000000-0000-0000-0000-000000000001"
    qa_user = UserContext(
        id=qa_user_id,
        email="qa@raguard.ai",
        role=Role.OWNER,
        tenant_id=qa_tenant_id,
        workspace_id=qa_user_id,
        is_active=True,
        is_verified=True,
    )

    async def override_current_user():
        return qa_user

    async def override_get_db():
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        yield mock_session

    mock_ws = MagicMock(spec=Workspace)
    mock_ws.id = qa_user_id
    mock_ws.public_id = "ws-qa-001"
    mock_ws.name = "QA Performance Workspace"
    mock_ws.slug = "qa-performance-workspace"
    mock_ws.status = WorkspaceStatus.ACTIVE.value
    mock_ws.description = "Offline performance test workspace"
    mock_ws.provisioning_status = "READY"
    mock_ws.updated_at = datetime.now(timezone.utc)

    mock_ws_repo = MagicMock()
    mock_ws_repo.get_by_id = AsyncMock(return_value=mock_ws)

    mock_member = MagicMock(spec=WorkspaceMember)
    mock_member.role = "OWNER"
    mock_member.joined_at = datetime.now(timezone.utc)

    mock_member_repo = MagicMock()
    mock_member_repo.get_membership = AsyncMock(return_value=mock_member)

    mock_profile_service = MagicMock()
    mock_user_response = UserResponse(
        id=qa_user_id,
        email="qa@raguard.ai",
        username="qa_lead",
        role="OWNER",
        is_active=True,
        avatar_url=None,
        profile_data={},
        preferences={},
        workspace_settings={},
    )
    mock_profile_service.get_profile = AsyncMock(return_value=mock_user_response)

    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_workspace_repository] = lambda: mock_ws_repo
    app.dependency_overrides[get_workspace_member_repository] = lambda: mock_member_repo
    app.dependency_overrides[get_user_profile_service] = lambda: mock_profile_service

    return app


@pytest.mark.asyncio
async def test_ci_performance_smoke_gate_rest_latency_ceiling(app_instance):
    """Assert operational latency ceiling T_max <= 500ms on core REST endpoints across N=20 samples.

    Master Plan Section 7.1(2):
    Disclaims statistical percentiles for N=20; strictly evaluates that every single sample satisfies
    T_max <= 500ms and that the suite completes in < 30.0 seconds.
    """
    mock_healthy_deps = {
        "postgresql": DependencyHealth(name="postgresql", status="healthy", latency_ms=1.2),
        "redis": DependencyHealth(name="redis", status="healthy", latency_ms=0.8),
        "qdrant": DependencyHealth(name="qdrant", status="healthy", latency_ms=1.5),
        "object_storage": DependencyHealth(name="object_storage", status="healthy", latency_ms=1.1),
        "llm_provider": DependencyHealth(name="llm_provider", status="healthy", latency_ms=2.0),
    }

    with patch("backend.api.v1.routes.health._check_dependencies", new_callable=AsyncMock) as mock_check:
        mock_check.return_value = mock_healthy_deps

        transport = httpx.ASGITransport(app=app_instance)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            target_endpoints = [
                ("GET", "/health/ready"),
                ("GET", "/api/v1/workspaces/current"),
                ("GET", "/api/v1/users/me"),
                ("GET", "/health"),
            ]

            # Warm-up pass across target endpoints to eliminate ASGI cold-start overhead
            for method, endpoint in target_endpoints:
                resp = await client.get(endpoint)
                assert resp.status_code == 200, f"Endpoint {endpoint} warm-up failed with {resp.status_code}: {resp.text}"

            suite_start = time.perf_counter()
            latencies_ms: dict[str, list[float]] = {ep[1]: [] for ep in target_endpoints}
            sample_count = 20

            for _ in range(sample_count):
                for method, endpoint in target_endpoints:
                    t0 = time.perf_counter()
                    if method == "GET":
                        resp = await client.get(endpoint)
                    t_sample_ms = (time.perf_counter() - t0) * 1000.0
                    latencies_ms[endpoint].append(t_sample_ms)

                    # Each sample must strictly adhere to the 500ms operational ceiling
                    assert t_sample_ms <= 500.0, (
                        f"Latency ceiling violated on {endpoint}: {t_sample_ms:.2f}ms > 500.0ms "
                        f"(Status: {resp.status_code})"
                    )

            suite_duration_s = time.perf_counter() - suite_start

            # Total suite execution runtime must be < 30.0s
            assert suite_duration_s < 30.0, (
                f"CI performance smoke suite duration {suite_duration_s:.2f}s exceeded 30.0s limit"
            )


@pytest.mark.asyncio
async def test_ci_performance_smoke_gate_chat_ttft_ceiling():
    """Assert nominal chat TTFT < 800ms using MockLLMProvider."""
    provider = MockLLMProvider(ttft_delay_seconds=0.200, token_delay_seconds=0.010)
    request = LLMRequest(prompt="Performance smoke benchmark prompt")

    start = time.perf_counter()
    first_token_received = False
    ttft_ms = 0.0

    async for chunk in provider.stream(request):
        if not first_token_received:
            first_token_received = True
            ttft_ms = (time.perf_counter() - start) * 1000.0
            break

    assert first_token_received is True
    # Nominal chat TTFT ceiling < 800ms
    assert ttft_ms < 800.0, f"Nominal TTFT was {ttft_ms:.2f}ms (must be < 800.0ms)"
