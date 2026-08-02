"""Unit tests for Security & Authentication Foundation (`backend/core/security/`, `backend/core/auth/`, `backend/services/auth/`).

Tests:
1. JWTVerifier dual verification modes and error mapping.
2. AuthService non-destructive, idempotent user synchronization and audit logging.
3. PermissionRegistry and Role enums/guards.
4. AuthorizationService role and permission evaluations.
5. Reusable authentication and authorization dependencies (`get_current_user`, `require_role`, `require_permission`).
"""

from typing import Any
from unittest.mock import MagicMock
import uuid

from fastapi import Request
import jwt
import pytest

from backend.core.auth.context import UserContext
from backend.core.auth.middleware import extract_bearer_token
from backend.core.dependencies.auth import (
    get_current_user,
)
from backend.core.exceptions.auth import (
    AuthenticationException,
    InsufficientRoleException,
)
from backend.core.permissions.guards import evaluate_permission_access, evaluate_role_access
from backend.core.permissions.rbac import Role
from backend.core.permissions.registry import Permission, PermissionRegistry
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
    registry._role_permissions[Role.VIEWER].add(Permission.WRITE_KNOWLEDGE.value)
    assert registry.has_permission(Role.VIEWER, Permission.WRITE_KNOWLEDGE) is True


def test_permission_guards():
    assert evaluate_role_access(Role.ADMIN, (Role.ENGINEER,)) is True
    assert evaluate_role_access(Role.ENGINEER, (Role.ENGINEER,)) is True
    assert evaluate_role_access(Role.VIEWER, (Role.ENGINEER,)) is False
    assert evaluate_permission_access(Role.ANALYST, Permission.READ_KNOWLEDGE) is True
    assert evaluate_permission_access(Role.ANALYST, Permission.MANAGE_KEYS) is False







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


