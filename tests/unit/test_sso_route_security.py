"""Unit tests for AUD-002: SSO Route Security and Workspace Scoping."""

from unittest.mock import AsyncMock, MagicMock
import uuid
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.v1.routes.sso import router as sso_router
from backend.core.auth.context import UserContext
from backend.core.dependencies.database import get_db
from backend.core.dependencies.rbac import require_role
from backend.core.exceptions.handlers import get_exception_handlers
from backend.core.permissions.rbac import Role
from backend.models.entities.identity_provider import IdentityProvider
from backend.models.entities.workspace import Workspace
from backend.repositories.workspace import WorkspaceRepository


@pytest.fixture
def sso_test_app():
    app = FastAPI()
    for exc_class, handler in get_exception_handlers():
        app.add_exception_handler(exc_class, handler)
    app.include_router(sso_router, prefix="/api/v1")
    return app


def test_list_idps_unauthenticated(sso_test_app):
    """AUD-002 Gate: Unauthenticated request must return 401 Unauthorized."""
    client = TestClient(sso_test_app)
    resp = client.get("/api/v1/workspaces/test-workspace/idp")
    assert resp.status_code == 401


def test_list_idps_viewer_forbidden(sso_test_app):
    """AUD-002 Gate: Non-admin workspace member must return 403 Forbidden."""
    from backend.core.dependencies.auth import get_current_user

    ws_id = str(uuid.uuid4())
    viewer_context = UserContext(
        id=uuid.uuid4(),
        email="viewer@example.com",
        role=Role.VIEWER,
        tenant_id=ws_id,
        workspace_id=ws_id,
    )

    sso_test_app.dependency_overrides[get_current_user] = lambda: viewer_context
    client = TestClient(sso_test_app)
    try:
        resp = client.get("/api/v1/workspaces/test-workspace/idp")
        assert resp.status_code == 403
    finally:
        sso_test_app.dependency_overrides.clear()


def test_list_idps_cross_tenant_forbidden(sso_test_app):
    """AUD-002 Gate: Admin of Workspace B querying Workspace A must return 403 Forbidden."""
    from backend.core.dependencies.auth import get_current_user

    ws_a_id = uuid.uuid4()
    ws_b_id = uuid.uuid4()

    admin_b_context = UserContext(
        id=uuid.uuid4(),
        email="admin_b@example.com",
        role=Role.ADMIN,
        tenant_id=str(ws_b_id),
        workspace_id=str(ws_b_id),
    )

    mock_ws_a = MagicMock(spec=Workspace)
    mock_ws_a.id = ws_a_id
    mock_ws_a.slug = "workspace-a"

    mock_session = AsyncMock()

    sso_test_app.dependency_overrides[get_current_user] = lambda: admin_b_context
    sso_test_app.dependency_overrides[get_db] = lambda: mock_session

    client = TestClient(sso_test_app)
    try:
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(WorkspaceRepository, "get_by_slug", AsyncMock(return_value=mock_ws_a))
            resp = client.get("/api/v1/workspaces/workspace-a/idp")
            assert resp.status_code == 403
            assert "Insufficient workspace membership" in resp.text
    finally:
        sso_test_app.dependency_overrides.clear()


def test_list_idps_success_admin(sso_test_app):
    """AUD-002 Gate: Admin of Workspace A querying Workspace A returns only Workspace A IdPs."""
    from datetime import UTC, datetime
    from backend.core.dependencies.auth import get_current_user

    ws_a_id = uuid.uuid4()

    admin_a_context = UserContext(
        id=uuid.uuid4(),
        email="admin_a@example.com",
        role=Role.ADMIN,
        tenant_id=str(ws_a_id),
        workspace_id=str(ws_a_id),
    )

    mock_ws_a = MagicMock(spec=Workspace)
    mock_ws_a.id = ws_a_id
    mock_ws_a.slug = "workspace-a"

    now = datetime.now(UTC)
    idp = MagicMock(spec=IdentityProvider)
    idp.id = uuid.uuid4()
    idp.workspace_id = ws_a_id
    idp.name = "Okta SAML"
    idp.type = "saml"
    idp.is_active = True
    idp.entity_id_issuer = "https://okta.example.com"
    idp.sso_url = "https://okta.example.com/sso"
    idp.logout_url = None
    idp.metadata_url = None
    idp.certificates = []
    idp.attribute_mapping = {}
    idp.domain_restrictions = []
    idp.jit_enabled = True
    idp.force_sso = False
    idp.created_at = now
    idp.updated_at = now

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [idp]

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    sso_test_app.dependency_overrides[get_current_user] = lambda: admin_a_context
    sso_test_app.dependency_overrides[get_db] = lambda: mock_session

    client = TestClient(sso_test_app)
    try:
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(WorkspaceRepository, "get_by_slug", AsyncMock(return_value=mock_ws_a))
            resp = client.get("/api/v1/workspaces/workspace-a/idp")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data) == 1
            assert data[0]["name"] == "Okta SAML"
            assert data[0]["workspace_id"] == str(ws_a_id)
    finally:
        sso_test_app.dependency_overrides.clear()
