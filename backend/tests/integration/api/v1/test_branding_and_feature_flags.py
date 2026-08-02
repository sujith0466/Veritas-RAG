"""Integration tests for F3.7 Branding and F3.8 Feature Flag API routes."""

from unittest.mock import AsyncMock, MagicMock
import uuid
import pytest
from fastapi.testclient import TestClient

from backend.core.auth.context import UserContext
from backend.core.permissions.rbac import Role
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import (
    get_feature_flag_evaluation_service,
    get_feature_flag_management_service,
    get_feature_flag_repository,
    get_workspace_settings_service,
)
from fastapi import FastAPI
from backend.api.v1.routes.workspaces import router as workspaces_router
from backend.api.v1.routes.feature_flags import (
    router as feature_flags_router,
    workspace_ff_router as workspace_feature_flags_router,
)

from datetime import datetime, timezone
from backend.models.entities.feature_flag import FeatureFlag
from backend.services.feature_flag.evaluation_service import EvaluationResult

app = FastAPI()
app.include_router(workspaces_router, prefix="/api/v1")
app.include_router(feature_flags_router, prefix="/api/v1")
app.include_router(workspace_feature_flags_router, prefix="/api/v1")


def get_mock_admin_user():
    return UserContext(
        id=uuid.uuid4(),
        email="admin@raguard.ai",
        role=Role.ADMIN,
        is_active=True,
        is_verified=True,
        supabase_id="mock-admin-supabase-id",
        session_id=uuid.uuid4(),
    )


def get_mock_regular_user():
    return UserContext(
        id=uuid.uuid4(),
        email="user@example.com",
        role=Role.VIEWER,
        is_active=True,
        is_verified=True,
        supabase_id="mock-user-supabase-id",
        session_id=uuid.uuid4(),
    )


from backend.core.dependencies.database import (
    get_db,
    get_feature_flag_evaluation_service,
    get_feature_flag_management_service,
    get_feature_flag_repository,
    get_workspace_settings_service,
)


def test_list_feature_flags_endpoint():
    mock_repo = AsyncMock()
    now = datetime.now(timezone.utc)
    mock_flag = FeatureFlag(
        id=uuid.uuid4(),
        key="fast_embeddings",
        name="Fast Embeddings",
        description="Fast embedding flag",
        category="RAG",
        lifecycle_state="ACTIVE",
        flag_type="BOOLEAN",
        default_enabled=True,
        is_killswitch_active=False,
        prerequisite_flag_keys=[],
        default_variant_json={},
        target_environments="production,staging",
        version=1,
        created_at=now,
        updated_at=now,
    )
    mock_repo.list_active_flags.return_value = [mock_flag]

    app.dependency_overrides[get_current_user] = get_mock_regular_user
    app.dependency_overrides[get_feature_flag_repository] = lambda: mock_repo

    client = TestClient(app)
    response = client.get("/api/v1/feature-flags")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["data"]) == 1
    assert data["data"][0]["key"] == "fast_embeddings"


def test_evaluate_workspace_flag_endpoint():
    workspace_id = uuid.uuid4()
    mock_eval_service = AsyncMock()
    mock_eval_service.evaluate_flag.return_value = EvaluationResult(
        flag_key="fast_embeddings",
        is_enabled=True,
        variant={},
        reason="GLOBAL_DEFAULT",
        tier_served="L1_MEMORY",
        evaluated_at=datetime.now(timezone.utc),
    )

    app.dependency_overrides[get_current_user] = get_mock_admin_user
    app.dependency_overrides[get_feature_flag_evaluation_service] = lambda: mock_eval_service

    client = TestClient(app)
    response = client.get(f"/api/v1/workspaces/{workspace_id}/feature-flags/fast_embeddings/evaluate")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["flag_key"] == "fast_embeddings"
    assert data["data"]["is_enabled"] is True
    assert data["data"]["tier_served"] == "L1_MEMORY"


def test_get_workspace_branding_endpoint():
    workspace_id = uuid.uuid4()
    mock_settings_service = AsyncMock()
    
    mock_settings_service.get_resolved_branding.return_value = {
        "workspace_id": workspace_id,
        "branding": {
            "primary_color": "#2563eb",
            "secondary_color": "#475569",
            "theme_mode": "DARK",
            "font_family": "Inter, sans-serif",
            "border_radius": "0.5rem",
        },
        "css_variables": {
            "--brand-primary": "#2563eb",
            "--brand-secondary": "#475569",
            "--brand-font-family": "Inter, sans-serif",
        },
        "css_string": ":root { --brand-primary: #2563eb; }",
        "tailwind_tokens": {"colors": {"brand": {"primary": "var(--brand-primary)"}}},
        "theme_mode": "DARK",
        "version": 2,
        "settings_hash": "testhash123",
        "is_preview": False,
    }

    app.dependency_overrides[get_current_user] = get_mock_admin_user
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    app.dependency_overrides[get_workspace_settings_service] = lambda: mock_settings_service

    client = TestClient(app)
    response = client.get(f"/api/v1/workspaces/{workspace_id}/branding")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["css_variables"]["--brand-primary"] == "#2563eb"
    assert data["data"]["theme_mode"] == "DARK"
