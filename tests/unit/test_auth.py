"""Unit tests for Security & Authentication Foundation (`backend/core/security/`, `backend/core/auth/`, `backend/services/auth/`).

Tests:
1. JWTVerifier dual verification modes and error mapping.
2. AuthService non-destructive, idempotent user synchronization and audit logging.
3. PermissionRegistry and Role enums/guards.
4. AuthorizationService role and permission evaluations.
5. Reusable authentication and authorization dependencies (`get_current_user`, `require_role`, `require_permission`).
"""

import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

from fastapi import Request
import jwt
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.auth.context import UserContext
from backend.core.auth.middleware import extract_bearer_token
from backend.core.dependencies.auth import (
    get_current_user,
    require_permission,
    require_role,
)
from backend.core.exceptions.auth import (
    AuthenticationException,
    ExpiredTokenException,
    InsufficientRoleException,
    InvalidTokenException,
)
from backend.core.permissions.guards import evaluate_permission_access, evaluate_role_access
from backend.core.permissions.rbac import Role
from backend.core.permissions.registry import Permission, PermissionRegistry
from backend.core.security.jwt import JWTVerifier
from backend.models.entities.user import User
from backend.services.auth.auth_service import AuthService
from backend.services.auth.authorization_service import AuthorizationService

SECRET = "test-jwt-secret"


def _make_token(claims: dict[str, Any], secret: str = SECRET, alg: str = "HS256") -> str:
    return jwt.encode(claims, key=secret, algorithm=alg)


# ── Test extract_bearer_token ──────────────────────────────────────────────────


def test_extract_bearer_token_valid():
    req = MagicMock(spec=Request)
    req.headers = {"Authorization": "Bearer my.jwt.token"}
    assert extract_bearer_token(req) == "my.jwt.token"


def test_extract_bearer_token_missing():
    req = MagicMock(spec=Request)
    req.headers = {}
    assert extract_bearer_token(req) is None


def test_extract_bearer_token_malformed():
    req = MagicMock(spec=Request)
    req.headers = {"Authorization": "Basic 123456"}
    assert extract_bearer_token(req) is None


# ── Test Role & PermissionRegistry ──────────────────────────────────────────────


def test_role_from_str():
    assert Role.from_str("admin") == Role.ADMIN
    assert Role.from_str("ENGINEER") == Role.ENGINEER
    assert Role.from_str("unknown_role") == Role.VIEWER
    assert Role.from_str(None) == Role.VIEWER


def test_permission_registry_default_mappings():
    registry = PermissionRegistry()
    assert registry.has_permission(Role.ADMIN, Permission.MANAGE_USERS) is True
    assert registry.has_permission(Role.ENGINEER, Permission.WRITE_KNOWLEDGE) is True
    assert registry.has_permission(Role.VIEWER, Permission.WRITE_KNOWLEDGE) is False
    assert registry.has_permission(Role.VIEWER, Permission.READ_KNOWLEDGE) is True


def test_permission_registry_custom_register():
    registry = PermissionRegistry()
    registry.register_role_permissions(Role.VIEWER, {Permission.WRITE_KNOWLEDGE})
    assert registry.has_permission(Role.VIEWER, Permission.WRITE_KNOWLEDGE) is True


def test_permission_guards():
    assert evaluate_role_access(Role.ADMIN, (Role.ENGINEER,)) is True
    assert evaluate_role_access(Role.ENGINEER, (Role.ENGINEER,)) is True
    assert evaluate_role_access(Role.VIEWER, (Role.ENGINEER,)) is False
    assert evaluate_permission_access(Role.ANALYST, Permission.READ_KNOWLEDGE) is True
    assert evaluate_permission_access(Role.ANALYST, Permission.MANAGE_KEYS) is False


# ── Test JWTVerifier ───────────────────────────────────────────────────────────


def test_jwt_verifier_secret_mode_valid():
    verifier = JWTVerifier()
    claims = {
        "sub": "user-uuid-123",
        "email": "engineer@raguard.ai",
        "role": "engineer",
        "exp": int(time.time()) + 3600,
    }
    token = _make_token(claims)
    payload = verifier.verify_and_decode(token)
    assert payload.sub == "user-uuid-123"
    assert payload.email == "engineer@raguard.ai"
    assert payload.role == "engineer"


def test_jwt_verifier_expired_token():
    verifier = JWTVerifier()
    claims = {
        "sub": "user-uuid-123",
        "exp": int(time.time()) - 3600,
    }
    token = _make_token(claims)
    with pytest.raises(ExpiredTokenException) as exc_info:
        verifier.verify_and_decode(token)
    assert exc_info.value.error_code == "AUTH_003"


def test_jwt_verifier_invalid_signature():
    verifier = JWTVerifier()
    claims = {"sub": "user-uuid-123", "exp": int(time.time()) + 3600}
    token = _make_token(claims, secret="wrong-secret")
    with pytest.raises(InvalidTokenException) as exc_info:
        verifier.verify_and_decode(token)
    assert exc_info.value.error_code == "AUTH_002"


def test_jwt_verifier_missing_sub():
    verifier = JWTVerifier()
    claims = {"email": "no_sub@raguard.ai", "exp": int(time.time()) + 3600}
    token = _make_token(claims)
    with pytest.raises(InvalidTokenException):
        verifier.verify_and_decode(token)


@patch("jwt.PyJWKClient")
def test_jwt_verifier_jwks_mode(mock_jwk_client_class, monkeypatch):
    monkeypatch.setenv("SUPABASE_JWKS_URL", "https://test.supabase.co/.well-known/jwks.json")
    from backend.core.config import get_settings

    get_settings.cache_clear()

    mock_client_instance = MagicMock()
    mock_jwk_client_class.return_value = mock_client_instance

    mock_key = MagicMock()
    mock_key.key = SECRET
    mock_client_instance.get_signing_key_from_jwt.return_value = mock_key

    verifier = JWTVerifier()
    assert verifier._jwk_client is not None

    claims = {"sub": "jwks-user-456", "exp": int(time.time()) + 3600}
    token = _make_token(claims)
    payload = verifier.verify_and_decode(token)
    assert payload.sub == "jwks-user-456"
    get_settings.cache_clear()


# ── Test AuthService ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_auth_service_idempotent_sync_first_login():
    mock_session = AsyncMock(spec=AsyncSession)
    service = AuthService(mock_session)

    claims = {
        "sub": "new-supabase-id",
        "email": "newuser@raguard.ai",
        "role": "engineer",
        "exp": int(time.time()) + 3600,
    }
    token = _make_token(claims)

    with patch.object(service.user_repo, "get_by_supabase_id", return_value=None), patch.object(
        service.user_repo,
        "create",
        return_value=User(
            id=uuid.uuid4(),
            supabase_user_id="new-supabase-id",
            email="newuser@raguard.ai",
            role="engineer",
            is_active=True,
        ),
    ) as mock_create, patch("backend.services.auth.auth_service.log_auth_event") as mock_audit:
        user_context = await service.authenticate_token(token)
        assert user_context.supabase_id == "new-supabase-id"
        assert user_context.email == "newuser@raguard.ai"
        assert user_context.role == Role.ENGINEER
        mock_create.assert_called_once_with(
            supabase_user_id="new-supabase-id",
            email="newuser@raguard.ai",
            role="engineer",
            is_active=True,
        )
        mock_audit.assert_called_once()


@pytest.mark.asyncio
async def test_auth_service_non_destructive_sync_existing_user():
    mock_session = AsyncMock(spec=AsyncSession)
    service = AuthService(mock_session)

    # JWT says role is 'viewer' and email is new, but DB user is already 'admin'
    claims = {
        "sub": "existing-supabase-id",
        "email": "updated@raguard.ai",
        "role": "viewer",
        "exp": int(time.time()) + 3600,
    }
    token = _make_token(claims)

    existing_user = User(
        id=uuid.uuid4(),
        supabase_user_id="existing-supabase-id",
        email="old@raguard.ai",
        role="admin",  # Internal application role
        is_active=True,
    )
    updated_user = User(
        id=existing_user.id,
        supabase_user_id="existing-supabase-id",
        email="updated@raguard.ai",
        role="admin",
        is_active=True,
    )

    with patch.object(
        service.user_repo, "get_by_supabase_id", return_value=existing_user
    ), patch.object(service.user_repo, "update", return_value=updated_user) as mock_update, patch(
        "backend.services.auth.auth_service.log_auth_event"
    ):
        user_context = await service.authenticate_token(token)
        # Verify only email updated and internal role preserved!
        mock_update.assert_called_once_with(existing_user, email="updated@raguard.ai")
        assert user_context.email == "updated@raguard.ai"
        assert user_context.role == Role.ADMIN


@pytest.mark.asyncio
async def test_auth_service_disabled_account_raises():
    mock_session = AsyncMock(spec=AsyncSession)
    service = AuthService(mock_session)

    claims = {"sub": "disabled-id", "exp": int(time.time()) + 3600}
    token = _make_token(claims)
    disabled_user = User(
        id=uuid.uuid4(),
        supabase_user_id="disabled-id",
        email="disabled@raguard.ai",
        role="viewer",
        is_active=False,
    )

    with (
        patch.object(service.user_repo, "get_by_supabase_id", return_value=disabled_user),
        patch("backend.services.auth.auth_service.log_auth_event"),
        pytest.raises(AuthenticationException, match="User account is disabled"),
    ):
        await service.authenticate_token(token)


# ── Test AuthorizationService ──────────────────────────────────────────────────


def test_authorization_service_check_and_verify():
    authz = AuthorizationService()
    admin = UserContext(
        id=uuid.uuid4(), supabase_id="s1", email="admin@raguard.ai", role=Role.ADMIN
    )
    viewer = UserContext(
        id=uuid.uuid4(), supabase_id="s2", email="viewer@raguard.ai", role=Role.VIEWER
    )

    assert authz.check_role(admin, Role.ENGINEER) is True
    assert authz.check_role(viewer, Role.ENGINEER) is False
    assert authz.check_permission(viewer, Permission.READ_KNOWLEDGE) is True
    assert authz.check_permission(viewer, Permission.WRITE_KNOWLEDGE) is False

    authz.verify_role(admin, Role.ENGINEER)  # does not raise
    with pytest.raises(InsufficientRoleException):
        authz.verify_role(viewer, Role.ENGINEER)

    authz.verify_permission(viewer, Permission.READ_KNOWLEDGE)  # does not raise
    with pytest.raises(InsufficientRoleException):
        authz.verify_permission(viewer, Permission.WRITE_KNOWLEDGE)


# ── Test Dependencies (`get_current_user`, `require_role`, `require_permission`)


@pytest.mark.asyncio
async def test_get_current_user_dependency():
    user = UserContext(
        id=uuid.uuid4(), supabase_id="sub", email="user@raguard.ai", role=Role.VIEWER
    )
    assert await get_current_user(user) == user

    with pytest.raises(AuthenticationException):
        await get_current_user(None)


@pytest.mark.asyncio
async def test_require_role_dependency():
    guard = require_role(Role.ENGINEER)
    engineer = UserContext(
        id=uuid.uuid4(), supabase_id="sub", email="e@raguard.ai", role=Role.ENGINEER
    )
    viewer = UserContext(
        id=uuid.uuid4(), supabase_id="sub", email="v@raguard.ai", role=Role.VIEWER
    )

    assert await guard(engineer) == engineer
    with pytest.raises(InsufficientRoleException):
        await guard(viewer)


@pytest.mark.asyncio
async def test_require_permission_dependency():
    guard = require_permission(Permission.RUN_QUERY)
    analyst = UserContext(
        id=uuid.uuid4(), supabase_id="sub", email="a@raguard.ai", role=Role.ANALYST
    )
    viewer = UserContext(
        id=uuid.uuid4(), supabase_id="sub", email="v@raguard.ai", role=Role.VIEWER
    )

    assert await guard(analyst) == analyst
    with pytest.raises(InsufficientRoleException):
        await guard(viewer)
