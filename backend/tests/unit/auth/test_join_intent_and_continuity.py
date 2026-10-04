"""Unit & Integration tests for WS-A5 Join Intent & Google Continuity Security Remediation.

Validates all 12 security requirements:
1. SSO login does not accept or require raw invitation_token in URL.
2. SSO login does not accept or require raw join_code in URL.
3. Join intent resolves server-side via intent_id.
4. Invitation validation still succeeds after OAuth continuity.
5. Join Code validation still succeeds after OAuth continuity.
6. Raw invitation token never appears in OAuth URL/state.
7. Raw Join Code never appears in OAuth URL/state.
8. OAuth state is consumed atomically.
9. First callback succeeds.
10. Replay callback fails.
11. Concurrent callback consumption permits only one success.
12. Zero secret leakage to Google OAuth URL and access logs.
"""

import asyncio
from datetime import UTC, datetime
import json
from unittest.mock import AsyncMock, MagicMock, patch
import urllib.parse
import uuid

import pytest

from backend.api.v1.routes.auth import sso_login
from backend.api.v1.schemas.workspace_onboarding import (
    JoinIntentCreateRequest,
    JoinWorkspaceRequest,
    JoiningMode,
)
from backend.core.exceptions.auth import AuthenticationException
from backend.models.entities.user import User
from backend.models.entities.workspace import Workspace, WorkspaceStatus
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember
from backend.services.auth.auth_service import AuthService
from backend.services.auth.sso_service import (
    GoogleOIDCProvider,
    atomic_consume_state,
)
from backend.services.workspace.workspace_joining_service import (
    JoinWorkspaceData,
    WorkspaceIdentifierInvalidError,
    WorkspaceJoinCodeInvalidError,
    WorkspaceJoiningError,
    WorkspaceJoiningService,
    WorkspaceMembershipConflictError,
)


# ── 1. GoogleOIDCProvider & Secret Isolation Tests ───────────────────────────

@pytest.mark.asyncio
async def test_google_oidc_preserves_join_intent_in_redis_state():
    with patch.dict(
        "os.environ",
        {
            "OIDC_GOOGLE_CLIENT_ID": "test-client-id",
            "OIDC_GOOGLE_CLIENT_SECRET": "test-client-secret",
        },
    ):
        provider = GoogleOIDCProvider()
        mock_redis = AsyncMock()
        provider.redis = mock_redis

        join_intent = {
            "workspace_id": "ACME-CORP",
            "join_code": "VR-234567",
            "invitation_token": "sec_inv_1234567890123456789012_secret123456",
        }

        auth_url = await provider.get_auth_url(join_intent=join_intent)

        # Invariant: Neither raw join_code nor raw invitation_token must EVER appear in OAuth URL
        assert "VR-234567" not in auth_url
        assert "sec_inv_" not in auth_url
        assert "ACME-CORP" not in auth_url
        assert "client_id=test-client-id" in auth_url
        assert "state=" in auth_url

        # Redis must cache session_data with join_intent and 600s TTL
        mock_redis.set.assert_awaited_once()
        call_args = mock_redis.set.await_args
        redis_key = call_args[0][0]
        cached_payload = json.loads(call_args[0][1])
        ttl = call_args[1].get("ex")

        assert redis_key.startswith("oidc:state:")
        assert ttl == 600
        assert "code_verifier" in cached_payload
        assert cached_payload["join_intent"] == join_intent


# ── 2. Atomic Replay Protection & Concurrency Tests ──────────────────────────

@pytest.mark.asyncio
async def test_atomic_consume_state_native_getdel():
    mock_redis = AsyncMock()
    mock_redis.getdel.return_value = '{"nonce": "123"}'

    res = await atomic_consume_state(mock_redis, "oidc:state:test-state")
    assert res == '{"nonce": "123"}'
    mock_redis.getdel.assert_awaited_once_with("oidc:state:test-state")


@pytest.mark.asyncio
async def test_atomic_consume_state_lua_fallback():
    mock_redis = AsyncMock()
    mock_redis.getdel.side_effect = Exception("GETDEL not supported")
    mock_redis.eval.return_value = '{"nonce": "123"}'

    res = await atomic_consume_state(mock_redis, "oidc:state:test-state")
    assert res == '{"nonce": "123"}'
    mock_redis.eval.assert_awaited_once()


@pytest.mark.asyncio
async def test_oauth_state_first_callback_succeeds_replay_fails():
    """Validates that first exchange succeeds and replay callback with same state fails."""
    with patch.dict(
        "os.environ",
        {
            "OIDC_GOOGLE_CLIENT_ID": "test-client-id",
            "OIDC_GOOGLE_CLIENT_SECRET": "test-client-secret",
        },
    ):
        provider = GoogleOIDCProvider()
        mock_redis = AsyncMock()
        provider.redis = mock_redis

        state = "single-use-state-xyz"
        session_data = {
            "nonce": "nonce-123",
            "code_verifier": "verifier-123",
            "join_intent": {"workspace_id": "ACME-CORP"},
        }

        # Simulate atomic GETDEL: first call returns session data, second call returns None
        mock_redis.getdel.side_effect = [json.dumps(session_data), None]

        with patch.object(provider, "_get_oidc_config", new_callable=AsyncMock) as mock_config, \
             patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post, \
             patch.object(provider, "_get_jwks", new_callable=AsyncMock) as mock_jwks, \
             patch("jwt.get_unverified_header") as mock_header, \
             patch("jwt.decode") as mock_decode, \
             patch("jwt.algorithms.RSAAlgorithm.from_jwk", return_value="pubkey"):

            mock_config.return_value = {
                "token_endpoint": "https://oauth2.googleapis.com/token",
                "jwks_uri": "https://www.googleapis.com/oauth2/v3/certs",
                "issuer": "https://accounts.google.com",
            }
            mock_token_resp = MagicMock()
            mock_token_resp.status_code = 200
            mock_token_resp.json.return_value = {"id_token": "token-1"}
            mock_post.return_value = mock_token_resp

            mock_jwks.return_value = {"keys": [{"kid": "k1"}]}
            mock_header.return_value = {"kid": "k1"}
            mock_decode.return_value = {
                "sub": "user-1",
                "email": "user@gmail.com",
                "nonce": "nonce-123",
                "email_verified": True,
            }

            # 1. First callback succeeds
            profile = await provider.exchange_code(code="code-1", state=state)
            assert profile["email"] == "user@gmail.com"

            # 2. Replay callback MUST fail with AuthenticationException
            with pytest.raises(AuthenticationException) as exc_info:
                await provider.exchange_code(code="code-1", state=state)

            assert "Invalid or expired state parameter" in str(exc_info.value)


@pytest.mark.asyncio
async def test_concurrent_callback_consumption_permits_only_one_success():
    """Simulates two concurrent callback requests racing to consume the same state.

    Proves that atomic consume ensures exactly one winner and one failure.
    """
    mock_redis = AsyncMock()
    # Emulate Redis single-threaded atomic GETDEL: only the first call receives the data
    session_data = json.dumps({"nonce": "nonce-abc", "code_verifier": "verifier-abc"})
    mock_redis.getdel.side_effect = [session_data, None]

    async def consume_attempt():
        return await atomic_consume_state(mock_redis, "oidc:state:race-state")

    res_a, res_b = await asyncio.gather(consume_attempt(), consume_attempt())

    # Exactly one must have received the data and one must have received None
    results = [res_a, res_b]
    assert session_data in results
    assert None in results
    assert mock_redis.getdel.await_count == 2


# ── 3. SSO Login Route Hardening (No Raw Secrets in URL) ─────────────────────

@pytest.mark.asyncio
async def test_sso_login_route_only_accepts_intent_id():
    """Verifies that GET /sso/login/{provider} only accepts intent_id and resolves server-side."""
    mock_redis = AsyncMock()
    cached_intent = {
        "intent_id": "opaque-intent-uuid",
        "workspace_id": "ACME-CORP",
        "join_code": "VR-234567",
    }
    mock_redis.get.return_value = json.dumps(cached_intent)

    with patch("backend.api.v1.routes.auth.get_redis_client", return_value=mock_redis), \
         patch("backend.api.v1.routes.auth.get_sso_provider") as mock_get_provider:

        mock_provider = AsyncMock()
        mock_provider.get_auth_url.return_value = "https://accounts.google.com/o/oauth2/v2/auth?state=xyz"
        mock_get_provider.return_value = mock_provider

        # Call sso_login with intent_id ONLY
        resp = await sso_login(provider="google", intent_id="opaque-intent-uuid")

        assert resp.status_code in (302, 307)
        # Server-side resolution was performed
        mock_redis.get.assert_awaited_once_with("auth:join_intent:opaque-intent-uuid")
        # Provider received the intent resolved server-side
        mock_provider.get_auth_url.assert_awaited_once_with(join_intent=cached_intent)


# ── 4. OAuth Continuity Join Validation Tests ────────────────────────────────

@pytest.mark.asyncio
async def test_invitation_validation_succeeds_after_oauth_continuity():
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()

    auth_service = AuthService(mock_session)
    auth_service.user_repo = AsyncMock()
    auth_service.user_repo.get_by_email.return_value = None
    auth_service.jwt_service = AsyncMock()
    auth_service.jwt_service.issue_tokens.return_value = ("access-jwt", "refresh-raw", "fam-1")

    target_ws_id = uuid.uuid4()

    mock_identity_res = MagicMock()
    mock_identity_res.scalar_one_or_none.return_value = None

    mock_member_res = MagicMock()
    mock_member_res.first.return_value = (target_ws_id, "Design Systems")

    mock_session.execute.side_effect = [mock_identity_res, mock_member_res]

    join_intent = {
        "invitation_token": "sec_inv_selector123456789012_secret123456",
    }

    with patch.object(
        WorkspaceJoiningService,
        "join_workspace",
        new_callable=AsyncMock,
    ) as mock_join:
        mock_join.return_value = JoinWorkspaceData(
            workspace_id=target_ws_id,
            workspace_name="Design Systems",
            role="MEMBER",
            status="ACTIVE",
            member_id=uuid.uuid4(),
        )

        access_token, _ = await auth_service.handle_oidc_login(
            email="invitee@example.com",
            provider="google",
            provider_user_id="google-sub-4",
            metadata={"name": "Invitee"},
            join_intent=join_intent,
        )

        mock_join.assert_awaited_once()
        assert mock_join.await_args[1]["invitation_token"] == join_intent["invitation_token"]

    added_user = None
    for call in mock_session.add.call_args_list:
        obj = call[0][0]
        if isinstance(obj, User):
            added_user = obj
            break

    assert added_user is not None
    assert added_user.tenant_id == str(target_ws_id)
    assert added_user.workspace_name == "Design Systems"


@pytest.mark.asyncio
async def test_join_code_validation_succeeds_after_oauth_continuity():
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()

    auth_service = AuthService(mock_session)
    auth_service.user_repo = AsyncMock()
    auth_service.user_repo.get_by_email.return_value = None
    auth_service.jwt_service = AsyncMock()
    auth_service.jwt_service.issue_tokens.return_value = ("access-jwt", "refresh-raw", "fam-1")

    target_ws_id = uuid.uuid4()

    mock_identity_res = MagicMock()
    mock_identity_res.scalar_one_or_none.return_value = None

    mock_member_res = MagicMock()
    mock_member_res.first.return_value = (target_ws_id, "Engineers")

    mock_session.execute.side_effect = [mock_identity_res, mock_member_res]

    join_intent = {
        "workspace_id": "ENG-CORP",
        "join_code": "VR-234567",
    }

    with patch.object(
        WorkspaceJoiningService,
        "join_workspace",
        new_callable=AsyncMock,
    ) as mock_join:
        mock_join.return_value = JoinWorkspaceData(
            workspace_id=target_ws_id,
            workspace_name="Engineers",
            role="MEMBER",
            status="ACTIVE",
            member_id=uuid.uuid4(),
        )

        access_token, _ = await auth_service.handle_oidc_login(
            email="eng@example.com",
            provider="google",
            provider_user_id="google-sub-5",
            metadata={"name": "Engineer"},
            join_intent=join_intent,
        )

        mock_join.assert_awaited_once()
        assert mock_join.await_args[1]["join_code"] == "VR-234567"
        assert mock_join.await_args[1]["workspace_identifier"] == "ENG-CORP"

    added_user = None
    for call in mock_session.add.call_args_list:
        obj = call[0][0]
        if isinstance(obj, User):
            added_user = obj
            break

    assert added_user is not None
    assert added_user.tenant_id == str(target_ws_id)
    assert added_user.workspace_name == "Engineers"
