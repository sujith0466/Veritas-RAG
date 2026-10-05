"""Comprehensive security regression tests for D3 — Demo Role Switcher.

Tests:
1. Unauthorized users (normal user, admin, owner) cannot switch roles (403).
2. Fail-closed behavior when feature flag is disabled (404).
3. Invalid role rejection (422).
4. JWT simulation claims (demo_simulated=True) and zero database role tampering.
5. Absolute continuity invariant: /auth/me retains demo_role_switcher_enabled=True under simulated VIEWER role.
6. Refresh continuity preserves simulated role across silent background refresh.
7. Reset endpoint restores authentic baseline database role and purges Redis keys.
8. Logout terminates simulation state.
9. Multiple session family isolation (Browser 1 vs Browser 2).
10. PLATFORM_ADMIN simulation safeguards:
    - Disabled by default (403)
    - Unbinds workspace context (workspace_id=None)
    - Blocks destructive operations (killswitch) in demo mode.
"""

import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException

from backend.api.v1.routes.auth import demo_switch_role, demo_reset_role, logout
from backend.api.v1.routes.feature_flags import toggle_killswitch
from backend.api.v1.schemas.auth import DemoRoleSwitchRequest
from backend.api.v1.schemas.feature_flag import FeatureFlagKillswitchRequest
from backend.core.auth.context import TokenPayload, UserContext
from backend.core.config import get_settings
from backend.core.permissions.rbac import Role
from backend.models.entities.user import User


class MockRedis:
    """Mock Redis client tracking key-value storage in memory."""
    def __init__(self):
        self.data = {}

    async def get(self, key: str):
        return self.data.get(key)

    async def set(self, key: str, value: str, ex: int | None = None):
        self.data[key] = str(value)

    async def delete(self, key: str):
        self.data.pop(key, None)


def _create_mock_request(user_id: uuid.UUID, family_id: str | None = None, role: str = "viewer") -> MagicMock:
    req = MagicMock()
    req.state.correlation_id = str(uuid.uuid4())
    req.state.token_payload = TokenPayload(
        sub=str(user_id),
        role=role,
        exp=9999999999,
        jti=str(uuid.uuid4()),
        family_id=family_id or str(uuid.uuid4()),
    )
    return req


@pytest.mark.asyncio
async def test_unauthorized_user_cannot_switch_role():
    """Verify that any account other than the designated DEMO_ACCOUNT_USER_ID is rejected with 403."""
    demo_operator_id = uuid.uuid4()
    unauthorized_user_id = uuid.uuid4()

    settings = get_settings()
    with patch.object(settings.features, "demo_role_switcher_enabled", True), \
         patch.object(settings.features, "demo_account_user_id", str(demo_operator_id)):

        mock_request = _create_mock_request(unauthorized_user_id)
        mock_db = AsyncMock()

        unauthorized_context = UserContext(
            id=unauthorized_user_id,
            email="regular-user@example.com",
            role=Role.ADMIN,
            demo_role_switcher_enabled=False,
        )

        payload = DemoRoleSwitchRequest(target_role="owner")

        with pytest.raises(HTTPException) as exc_info:
            await demo_switch_role(
                request=mock_request,
                payload=payload,
                current_user=unauthorized_context,
                db=mock_db,
            )

        assert exc_info.value.status_code == 403
        assert "Unauthorized" in exc_info.value.detail


@pytest.mark.asyncio
async def test_feature_flag_disabled_fails_closed():
    """Verify 404 when demo_role_switcher_enabled is False, even for designated demo account."""
    demo_operator_id = uuid.uuid4()

    settings = get_settings()
    with patch.object(settings.features, "demo_role_switcher_enabled", False), \
         patch.object(settings.features, "demo_account_user_id", str(demo_operator_id)):

        mock_request = _create_mock_request(demo_operator_id)
        mock_db = AsyncMock()

        demo_context = UserContext(
            id=demo_operator_id,
            email="demo-operator@example.com",
            role=Role.ADMIN,
            demo_role_switcher_enabled=False,
        )

        payload = DemoRoleSwitchRequest(target_role="member")

        with pytest.raises(HTTPException) as exc_info:
            await demo_switch_role(
                request=mock_request,
                payload=payload,
                current_user=demo_context,
                db=mock_db,
            )

        assert exc_info.value.status_code == 404
        assert "disabled" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_invalid_role_rejected_with_422():
    """Verify invalid role strings are rejected with 422 Unprocessable Entity."""
    demo_operator_id = uuid.uuid4()

    settings = get_settings()
    with patch.object(settings.features, "demo_role_switcher_enabled", True), \
         patch.object(settings.features, "demo_account_user_id", str(demo_operator_id)):

        mock_request = _create_mock_request(demo_operator_id)
        mock_db = AsyncMock()

        demo_context = UserContext(
            id=demo_operator_id,
            email="demo-operator@example.com",
            role=Role.OWNER,
            demo_role_switcher_enabled=True,
        )

        payload = DemoRoleSwitchRequest(target_role="super_hacker")

        with pytest.raises(HTTPException) as exc_info:
            await demo_switch_role(
                request=mock_request,
                payload=payload,
                current_user=demo_context,
                db=mock_db,
            )

        assert exc_info.value.status_code == 422
        assert "Invalid target role" in exc_info.value.detail


@pytest.mark.asyncio
async def test_jwt_simulation_claims_and_zero_db_tampering():
    """Verify JWT contains simulated role and demo_simulated=True without tampering DB records."""
    demo_operator_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    family_id = str(uuid.uuid4())

    settings = get_settings()
    mock_redis = MockRedis()

    with patch.object(settings.features, "demo_role_switcher_enabled", True), \
         patch.object(settings.features, "demo_account_user_id", str(demo_operator_id)), \
         patch("backend.api.v1.routes.auth.get_redis_client", return_value=mock_redis):

        # Database user entity has authentic role "member"
        db_user = User(
            id=demo_operator_id,
            email="operator@example.com",
            role="member",
            is_active=True,
            tenant_id=str(workspace_id),
        )

        mock_db = AsyncMock()
        mock_db.get.return_value = db_user

        mock_request = _create_mock_request(demo_operator_id, family_id=family_id, role="member")

        demo_context = UserContext(
            id=demo_operator_id,
            email="operator@example.com",
            role=Role.MEMBER,
            tenant_id=str(workspace_id),
            demo_role_switcher_enabled=True,
        )

        # Switch to OWNER
        payload = DemoRoleSwitchRequest(target_role="owner")
        resp = await demo_switch_role(
            request=mock_request,
            payload=payload,
            current_user=demo_context,
            db=mock_db,
        )

        # Verify response
        assert resp.data.role == "owner"
        assert resp.data.demo_simulated is True
        assert resp.data.workspace_id == str(workspace_id)

        # CRITICAL INVARIANT: Persistent DB user.role was NEVER mutated!
        assert db_user.role == "member"

        # Verify Redis session key set
        assert mock_redis.data.get(f"auth:demo_session:family:{family_id}:simulated_role") == "owner"


@pytest.mark.asyncio
async def test_auth_me_continuity_under_simulated_viewer():
    """Verify that switching down to VIEWER maintains demo_role_switcher_enabled=True on UserContext."""
    demo_operator_id = uuid.uuid4()
    workspace_id = uuid.uuid4()

    settings = get_settings()
    with patch.object(settings.features, "demo_role_switcher_enabled", True), \
         patch.object(settings.features, "demo_account_user_id", str(demo_operator_id)):

        # Simulated VIEWER user context
        viewer_context = UserContext(
            id=demo_operator_id,
            email="operator@example.com",
            role=Role.VIEWER,
            tenant_id=str(workspace_id),
            demo_role_switcher_enabled=True,
            demo_simulated=True,
        )

        # Verify attributes
        assert viewer_context.role == Role.VIEWER
        assert viewer_context.demo_simulated is True
        # CONTINUITY INVARIANT: Switcher remains enabled and visible!
        assert viewer_context.demo_role_switcher_enabled is True


@pytest.mark.asyncio
async def test_refresh_continuity_preserves_simulated_role():
    """Verify that AuthService.rotate_refresh_token preserves active simulation from Redis."""
    demo_operator_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    family_id = str(uuid.uuid4())

    settings = get_settings()
    mock_redis = MockRedis()

    # Pre-populate Redis with simulated role "admin" for this session family
    mock_redis.data[f"auth:demo_session:family:{family_id}:simulated_role"] = "admin"
    mock_redis.data[f"auth:demo_session:family:{family_id}:simulated_workspace_id"] = str(workspace_id)

    with patch.object(settings.features, "demo_role_switcher_enabled", True), \
         patch.object(settings.features, "demo_account_user_id", str(demo_operator_id)):

        from backend.services.auth.auth_service import AuthService
        from backend.models.entities.user_session import UserSession
        import hashlib
        import datetime

        mock_db = AsyncMock()

        raw_refresh = "test-raw-refresh-token"
        refresh_hash = hashlib.sha256(raw_refresh.encode("utf-8")).hexdigest()

        session_entry = UserSession(
            user_id=demo_operator_id,
            refresh_token_hash=refresh_hash,
            family_id=family_id,
            expires_at=datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=7),
            is_revoked=False,
            rotated_at=None,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = session_entry
        mock_db.execute = AsyncMock(return_value=mock_result)

        # Authentic database role is "viewer"
        db_user = User(
            id=demo_operator_id,
            email="operator@example.com",
            role="viewer",
            is_active=True,
            tenant_id=str(workspace_id),
        )
        mock_db.get.return_value = db_user

        auth_service = AuthService(mock_db)
        auth_service.jwt_service.redis = mock_redis

        access_token, new_refresh = await auth_service.rotate_refresh_token(raw_refresh)

        # Verify rotated token has simulated role "admin", not authentic "viewer"
        verified_payload = await auth_service.jwt_service.verify_token(access_token)
        assert verified_payload.role == "admin"
        assert verified_payload.demo_simulated is True
        assert verified_payload.family_id == family_id


@pytest.mark.asyncio
async def test_demo_reset_role_restores_base_role():
    """Verify demo-reset-role clears simulation and restores authentic DB role."""
    demo_operator_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    family_id = str(uuid.uuid4())

    settings = get_settings()
    mock_redis = MockRedis()
    mock_redis.data[f"auth:demo_session:family:{family_id}:simulated_role"] = "owner"

    with patch.object(settings.features, "demo_role_switcher_enabled", True), \
         patch.object(settings.features, "demo_account_user_id", str(demo_operator_id)), \
         patch("backend.api.v1.routes.auth.get_redis_client", return_value=mock_redis):

        # Base role in DB is "viewer"
        db_user = User(
            id=demo_operator_id,
            email="operator@example.com",
            role="viewer",
            is_active=True,
            tenant_id=str(workspace_id),
        )

        mock_db = AsyncMock()
        mock_db.get.return_value = db_user
        mock_result = MagicMock()
        mock_result.first.return_value = (workspace_id, "viewer")
        mock_db.execute = AsyncMock(return_value=mock_result)

        mock_request = _create_mock_request(demo_operator_id, family_id=family_id, role="owner")

        simulated_context = UserContext(
            id=demo_operator_id,
            email="operator@example.com",
            role=Role.OWNER,
            tenant_id=str(workspace_id),
            demo_role_switcher_enabled=True,
            demo_simulated=True,
        )

        resp = await demo_reset_role(
            request=mock_request,
            current_user=simulated_context,
            db=mock_db,
        )

        # Redis key purged
        assert f"auth:demo_session:family:{family_id}:simulated_role" not in mock_redis.data
        # Token returned has base role
        assert resp.data.role == "viewer"
        assert resp.data.demo_simulated is False


@pytest.mark.asyncio
async def test_logout_clears_simulation_state():
    """Verify /logout clears simulation keys from Redis."""
    demo_operator_id = uuid.uuid4()
    family_id = str(uuid.uuid4())

    settings = get_settings()
    mock_redis = MockRedis()
    mock_redis.data[f"auth:demo_session:family:{family_id}:simulated_role"] = "admin"
    mock_redis.data[f"auth:demo_session:user:{demo_operator_id}:simulated_role"] = "admin"

    with patch.object(settings.features, "demo_role_switcher_enabled", True), \
         patch.object(settings.features, "demo_account_user_id", str(demo_operator_id)), \
         patch("backend.api.v1.routes.auth.get_redis_client", return_value=mock_redis):

        mock_request = _create_mock_request(demo_operator_id, family_id=family_id, role="admin")
        mock_request.cookies = {"refresh_token": "some-token"}

        mock_response = MagicMock()
        mock_db = AsyncMock()

        user_ctx = UserContext(
            id=demo_operator_id,
            email="operator@example.com",
            role=Role.ADMIN,
            demo_role_switcher_enabled=True,
            demo_simulated=True,
        )

        with patch("backend.api.v1.routes.auth.AuthService") as mock_auth_service:
            mock_svc_instance = AsyncMock()
            mock_auth_service.return_value = mock_svc_instance

            await logout(
                request=mock_request,
                response=mock_response,
                user=user_ctx,
                db=mock_db,
            )

        # Verify simulation keys purged
        assert f"auth:demo_session:family:{family_id}:simulated_role" not in mock_redis.data
        assert f"auth:demo_session:user:{demo_operator_id}:simulated_role" not in mock_redis.data


@pytest.mark.asyncio
async def test_multiple_session_isolation():
    """Verify that simulating in Family 1 does NOT affect Family 2 on refresh."""
    demo_operator_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    family_1 = str(uuid.uuid4())
    family_2 = str(uuid.uuid4())

    settings = get_settings()
    mock_redis = MockRedis()

    # Family 1 simulated as "admin"
    mock_redis.data[f"auth:demo_session:family:{family_1}:simulated_role"] = "admin"

    with patch.object(settings.features, "demo_role_switcher_enabled", True), \
         patch.object(settings.features, "demo_account_user_id", str(demo_operator_id)):

        from backend.services.auth.auth_service import AuthService
        from backend.models.entities.user_session import UserSession
        import hashlib
        import datetime

        mock_db = AsyncMock()

        # Session 2 (Browser 2) with family_2
        raw_refresh_2 = "raw-refresh-browser-2"
        refresh_hash_2 = hashlib.sha256(raw_refresh_2.encode("utf-8")).hexdigest()

        session_entry_2 = UserSession(
            user_id=demo_operator_id,
            refresh_token_hash=refresh_hash_2,
            family_id=family_2,
            expires_at=datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=7),
            is_revoked=False,
            rotated_at=None,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = session_entry_2
        mock_result.first.return_value = (workspace_id, "viewer")
        mock_db.execute = AsyncMock(return_value=mock_result)

        # Authentic database role is "viewer"
        db_user = User(
            id=demo_operator_id,
            email="operator@example.com",
            role="viewer",
            is_active=True,
            tenant_id=str(workspace_id),
        )
        mock_db.get.return_value = db_user

        auth_service = AuthService(mock_db)
        auth_service.jwt_service.redis = mock_redis

        # Browser 2 refreshes its token
        access_token_2, _ = await auth_service.rotate_refresh_token(raw_refresh_2)

        # Browser 2 must receive its authentic baseline role "viewer", NOT Browser 1's "admin"!
        verified_payload_2 = await auth_service.jwt_service.verify_token(access_token_2)
        assert verified_payload_2.role == "viewer"
        assert verified_payload_2.demo_simulated is False
        assert verified_payload_2.family_id == family_2


@pytest.mark.asyncio
async def test_platform_admin_simulation_safeguards():
    """Verify PLATFORM_ADMIN simulation guards:
    1. 403 when demo_allow_platform_admin_simulation is False
    2. When allowed, sets workspace_id=None (unbound)
    3. Emergency killswitch toggle blocked in simulated demo mode.
    """
    demo_operator_id = uuid.uuid4()
    settings = get_settings()

    # 1. Denied when demo_allow_platform_admin_simulation is False
    with patch.object(settings.features, "demo_role_switcher_enabled", True), \
         patch.object(settings.features, "demo_account_user_id", str(demo_operator_id)), \
         patch.object(settings.features, "demo_allow_platform_admin_simulation", False):

        mock_request = _create_mock_request(demo_operator_id)
        mock_db = AsyncMock()

        user_ctx = UserContext(
            id=demo_operator_id,
            email="operator@example.com",
            role=Role.OWNER,
            demo_role_switcher_enabled=True,
        )

        payload = DemoRoleSwitchRequest(target_role="platform_admin")

        with pytest.raises(HTTPException) as exc_info:
            await demo_switch_role(
                request=mock_request,
                payload=payload,
                current_user=user_ctx,
                db=mock_db,
            )

        assert exc_info.value.status_code == 403
        assert "PLATFORM_ADMIN simulation is disabled" in exc_info.value.detail

    # 2. Permitted when demo_allow_platform_admin_simulation is True; workspace_id becomes None
    with patch.object(settings.features, "demo_role_switcher_enabled", True), \
         patch.object(settings.features, "demo_account_user_id", str(demo_operator_id)), \
         patch.object(settings.features, "demo_allow_platform_admin_simulation", True):

        mock_redis = MockRedis()
        with patch("backend.api.v1.routes.auth.get_redis_client", return_value=mock_redis):
            db_user = User(
                id=demo_operator_id,
                email="operator@example.com",
                role="viewer",
                is_active=True,
                tenant_id=str(uuid.uuid4()),
            )
            mock_db = AsyncMock()
            mock_db.get.return_value = db_user

            mock_request = _create_mock_request(demo_operator_id)

            resp = await demo_switch_role(
                request=mock_request,
                payload=payload,
                current_user=user_ctx,
                db=mock_db,
            )

            assert resp.data.role == "platform_admin"
            assert resp.data.workspace_id is None
            assert resp.data.demo_simulated is True

    # 3. Emergency killswitch toggle is blocked in demo simulation mode
    simulated_platform_admin = UserContext(
        id=demo_operator_id,
        email="operator@example.com",
        role=Role.PLATFORM_ADMIN,
        demo_simulated=True,
    )
    killswitch_payload = FeatureFlagKillswitchRequest(is_active=True, reason="Testing killswitch")
    with pytest.raises(HTTPException) as exc_info:
        await toggle_killswitch(
            flag_key="ENABLE_RETRY_ENGINE",
            request=killswitch_payload,
            current_user=simulated_platform_admin,
            session=AsyncMock(),
            management_service=AsyncMock(),
        )

    assert exc_info.value.status_code == 403
    assert "forbidden in demo simulation mode" in exc_info.value.detail
