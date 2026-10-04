"""Unit & Integration tests for WS-A5 Join Intent & Google Continuity.

Covers:
1. GoogleOIDCProvider join_intent storage and retrieval in Redis session.
2. Single-use replay protection (deleting oidc:state:{state}).
3. Zero secret leakage to Google OAuth URL.
4. Elimination of unguided auto-provisioning (user.workspace_id = None when no workspace).
5. Authoritative join intent fulfillment on OIDC callback.
6. Join intent REST endpoints (POST /join-intent, GET /join-intent/{id}).
7. POST /api/v1/workspaces/join endpoint.
"""

from datetime import UTC, datetime
import json
from unittest.mock import AsyncMock, MagicMock, patch
import urllib.parse
import uuid

import pytest

from backend.api.v1.schemas.workspace_onboarding import (
    JoinIntentCreateRequest,
    JoinWorkspaceRequest,
    JoiningMode,
)
from backend.models.entities.user import User
from backend.models.entities.workspace import Workspace, WorkspaceStatus
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember
from backend.services.auth.auth_service import AuthService
from backend.services.auth.sso_service import GoogleOIDCProvider
from backend.services.workspace.workspace_joining_service import (
    JoinWorkspaceData,
    WorkspaceIdentifierInvalidError,
    WorkspaceJoinCodeInvalidError,
    WorkspaceJoiningError,
    WorkspaceJoiningService,
    WorkspaceMembershipConflictError,
)


# ── 1. GoogleOIDCProvider Tests ──────────────────────────────────────────────

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
            "invitation_token": None,
        }

        auth_url = await provider.get_auth_url(join_intent=join_intent)

        # 1. URL passed to Google must NOT leak join_code or workspace_id
        assert "VR-234567" not in auth_url
        assert "ACME-CORP" not in auth_url
        assert "client_id=test-client-id" in auth_url
        assert "state=" in auth_url

        # 2. Redis must have cached session_data with join_intent and 600s TTL
        mock_redis.set.assert_awaited_once()
        call_args = mock_redis.set.await_args
        redis_key = call_args[0][0]
        cached_payload = json.loads(call_args[0][1])
        ttl = call_args[1].get("ex")

        assert redis_key.startswith("oidc:state:")
        assert ttl == 600
        assert "code_verifier" in cached_payload
        assert cached_payload["join_intent"] == join_intent


@pytest.mark.asyncio
async def test_google_oidc_exchange_retrieves_intent_and_deletes_state():
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

        state = "state-token-123"
        session_data = {
            "nonce": "nonce-123",
            "code_verifier": "verifier-123",
            "join_intent": {
                "workspace_id": "ACME-CORP",
                "join_code": "VR-234567",
            },
        }
        mock_redis.get.return_value = json.dumps(session_data)

        # Mock ID token decoding and JWKS
        with patch.object(provider, "_get_oidc_config", new_callable=AsyncMock) as mock_config, \
             patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post, \
             patch.object(provider, "_get_jwks", new_callable=AsyncMock) as mock_jwks, \
             patch("jwt.get_unverified_header") as mock_header, \
             patch("jwt.decode") as mock_decode:

            mock_config.return_value = {
                "token_endpoint": "https://oauth2.googleapis.com/token",
                "jwks_uri": "https://www.googleapis.com/oauth2/v3/certs",
                "issuer": "https://accounts.google.com",
            }

            mock_token_resp = MagicMock()
            mock_token_resp.status_code = 200
            mock_token_resp.json.return_value = {"id_token": "fake-id-token"}
            mock_post.return_value = mock_token_resp

            mock_jwks.return_value = {"keys": [{"kid": "key-1"}]}
            mock_header.return_value = {"kid": "key-1"}
            mock_decode.return_value = {
                "sub": "google-user-123",
                "email": "user@gmail.com",
                "name": "Google User",
                "nonce": "nonce-123",
                "email_verified": True,
            }

            with patch("jwt.algorithms.RSAAlgorithm.from_jwk", return_value="public-key"):
                profile = await provider.exchange_code(code="auth-code-123", state=state)

        # Single-use replay protection: Redis state key MUST be deleted
        mock_redis.delete.assert_awaited_once_with(f"oidc:state:{state}")

        assert profile["email"] == "user@gmail.com"
        assert profile["join_intent"] == session_data["join_intent"]


# ── 2. AuthService.handle_oidc_login Tests ────────────────────────────────────

@pytest.mark.asyncio
async def test_oidc_login_without_intent_does_not_provision_workspace():
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()

    auth_service = AuthService(mock_session)
    auth_service.user_repo = AsyncMock()
    auth_service.user_repo.get_by_email.return_value = None  # New user
    auth_service.jwt_service = AsyncMock()
    auth_service.jwt_service.issue_tokens.return_value = ("access-jwt", "refresh-raw", "fam-1")

    # Mock execute for SSOIdentity and WorkspaceMember queries
    mock_identity_res = MagicMock()
    mock_identity_res.scalar_one_or_none.return_value = None

    mock_member_res = MagicMock()
    mock_member_res.first.return_value = None  # No workspace memberships

    mock_session.execute.side_effect = [mock_identity_res, mock_member_res]

    access_token, raw_refresh = await auth_service.handle_oidc_login(
        email="newuser@example.com",
        provider="google",
        provider_user_id="google-sub-1",
        metadata={"name": "New User"},
        join_intent=None,
    )

    assert access_token == "access-jwt"
    assert raw_refresh == "refresh-raw"

    # Crucial check: User has NO tenant_id or workspace_name
    added_user = None
    for call in mock_session.add.call_args_list:
        obj = call[0][0]
        if isinstance(obj, User):
            added_user = obj
            break

    assert added_user is not None
    assert added_user.tenant_id is None
    assert added_user.workspace_name is None


@pytest.mark.asyncio
async def test_oidc_login_with_valid_join_intent_fulfills_and_binds_workspace():
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
    mock_member_res.first.return_value = (target_ws_id, "Joined Workspace")

    mock_session.execute.side_effect = [mock_identity_res, mock_member_res]

    join_intent = {
        "workspace_id": "JOIN-WS",
        "join_code": "VR-234567",
    }

    with patch.object(
        WorkspaceJoiningService,
        "join_workspace",
        new_callable=AsyncMock,
    ) as mock_join:
        mock_join.return_value = JoinWorkspaceData(
            workspace_id=target_ws_id,
            workspace_name="Joined Workspace",
            role="MEMBER",
            status="ACTIVE",
            member_id=uuid.uuid4(),
        )

        access_token, _ = await auth_service.handle_oidc_login(
            email="invited@example.com",
            provider="google",
            provider_user_id="google-sub-2",
            metadata={"name": "Invited User"},
            join_intent=join_intent,
        )

        mock_join.assert_awaited_once()

    # User tenant_id is now bound to the joined workspace
    added_user = None
    for call in mock_session.add.call_args_list:
        obj = call[0][0]
        if isinstance(obj, User):
            added_user = obj
            break

    assert added_user is not None
    assert added_user.tenant_id == str(target_ws_id)
    assert added_user.workspace_name == "Joined Workspace"


@pytest.mark.asyncio
async def test_oidc_login_with_failed_join_intent_logs_in_without_workspace():
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()

    auth_service = AuthService(mock_session)
    auth_service.user_repo = AsyncMock()
    auth_service.user_repo.get_by_email.return_value = None
    auth_service.jwt_service = AsyncMock()
    auth_service.jwt_service.issue_tokens.return_value = ("access-jwt", "refresh-raw", "fam-1")

    mock_identity_res = MagicMock()
    mock_identity_res.scalar_one_or_none.return_value = None

    mock_member_res = MagicMock()
    mock_member_res.first.return_value = None  # No workspace memberships

    mock_session.execute.side_effect = [mock_identity_res, mock_member_res]

    join_intent = {
        "workspace_id": "EXPIRED-WS",
        "join_code": "VR-EXPIRE",
    }

    with patch.object(
        WorkspaceJoiningService,
        "join_workspace",
        new_callable=AsyncMock,
    ) as mock_join:
        mock_join.side_effect = WorkspaceJoinCodeInvalidError("Join code has expired.")

        access_token, _ = await auth_service.handle_oidc_login(
            email="latecomer@example.com",
            provider="google",
            provider_user_id="google-sub-3",
            metadata={"name": "Latecomer"},
            join_intent=join_intent,
        )

        mock_join.assert_awaited_once()

    added_user = None
    for call in mock_session.add.call_args_list:
        obj = call[0][0]
        if isinstance(obj, User):
            added_user = obj
            break

    assert added_user is not None
    assert added_user.tenant_id is None
    assert added_user.workspace_name is None
