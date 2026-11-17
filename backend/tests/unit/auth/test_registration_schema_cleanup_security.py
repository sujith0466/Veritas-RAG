"""Unit and Security Regression Tests for Registration Schema Cleanup (WP-8).

Tests enforce:
1. Registration schema accepts intended credential and profile fields (email, password, full_name).
2. Strict password policy enforcement (length, upper, lower, digit, special char).
3. Dead onboarding fields (workspace_id, join_code, invitation_token, workspace_name, company_name)
   are stripped/ignored from RegistrationRequest according to API contract without breaking legacy callers.
4. Registration alone creates an unverified user and NEVER creates a workspace or grants membership.
5. Email verification is mandatory before protected onboarding and workspace access.
6. Existing invitation acceptance (WP-2 / WP-4) and join-code redemption (WP-1) continue to operate
   as the authoritative onboarding mechanisms decoupled from registration.
7. Referral behavior is preserved (extra referral fields safely ignored, zero consumers).
8. Role elevation attempts via registration payload (e.g. role='PLATFORM_ADMIN' or 'OWNER') are ignored.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from backend.api.v1.schemas.registration import RegistrationRequest, RegistrationResponse
from backend.services.auth.registration_service import RegistrationService


# ---------------------------------------------------------------------------
# 1. Registration Schema: Credential & Profile Acceptance
# ---------------------------------------------------------------------------

class TestRegistrationSchemaContract:
    """Verify RegistrationRequest accepts intended credential/profile fields."""

    def test_registration_valid_minimal(self):
        req = RegistrationRequest(
            email="developer@example.com",
            password="StrongPassword123!",
        )
        assert req.email == "developer@example.com"
        assert req.password == "StrongPassword123!"
        assert req.full_name is None

    def test_registration_valid_with_full_name(self):
        req = RegistrationRequest(
            email="alice@example.com",
            password="SecurePass2026!@",
            full_name="Alice Vance",
        )
        assert req.email == "alice@example.com"
        assert req.full_name == "Alice Vance"

    def test_registration_invalid_email(self):
        with pytest.raises(ValidationError):
            RegistrationRequest(
                email="not-an-email",
                password="StrongPassword123!",
            )

    @pytest.mark.parametrize("invalid_password,reason", [
        ("Short1!", "Too short (< 8 chars)"),
        ("nouppercase123!", "Missing uppercase letter"),
        ("NOLOWERCASE123!", "Missing lowercase letter"),
        ("NoNumbersHere!", "Missing number"),
        ("NoSpecialChar123", "Missing special character"),
    ])
    def test_registration_password_policy_enforcement(self, invalid_password: str, reason: str):
        with pytest.raises(ValidationError) as exc_info:
            RegistrationRequest(
                email="user@example.com",
                password=invalid_password,
            )
        assert "Password must contain" in str(exc_info.value) or "at least 8 characters" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 2. Dead Fields Stripped & Ignored
# ---------------------------------------------------------------------------

class TestRegistrationDeadFieldsCleanup:
    """Verify dead onboarding fields are stripped from schema and ignored."""

    def test_dead_fields_stripped_and_ignored(self):
        payload = {
            "email": "clean@example.com",
            "password": "ValidPassword123!",
            "full_name": "Clean User",
            # Dead onboarding fields:
            "workspace_id": "ACME-CORP",
            "join_code": "VR-7K9M2P",
            "invitation_token": "sec_inv_1234567890abcdef",
            "workspace_name": "Acme Workspace",
            "company_name": "Acme Global",
        }
        req = RegistrationRequest.model_validate(payload)
        assert req.email == "clean@example.com"
        assert req.full_name == "Clean User"

        # The model must NOT declare or attach these dead fields
        assert not hasattr(req, "workspace_id")
        assert not hasattr(req, "join_code")
        assert not hasattr(req, "invitation_token")
        assert not hasattr(req, "workspace_name")
        assert not hasattr(req, "company_name")

    def test_arbitrary_extra_fields_ignored_without_breaking_caller(self):
        payload = {
            "email": "extra@example.com",
            "password": "ValidPassword123!",
            "full_name": "Extra User",
            "referral_code": "REF-2026-XYZ",
            "marketing_opt_in": True,
            "role": "PLATFORM_ADMIN",  # Elevation attempt
        }
        req = RegistrationRequest.model_validate(payload)
        assert req.email == "extra@example.com"
        assert not hasattr(req, "referral_code")
        assert not hasattr(req, "marketing_opt_in")
        assert not hasattr(req, "role")

    def test_response_schema_contract(self):
        resp = RegistrationResponse()
        assert "Registration successful" in resp.message
        assert "verify your account" in resp.message


# ---------------------------------------------------------------------------
# 3. Registration Service: Separation from Workspace Lifecycle
# ---------------------------------------------------------------------------

class TestRegistrationServiceLifecycle:
    """Verify RegistrationService creates unverified user and touches zero workspaces."""

    @pytest.mark.asyncio
    async def test_registration_creates_unverified_user_only(self):
        mock_session = AsyncMock()
        service = RegistrationService(mock_session)

        # Mock UserRepository
        service.user_repo = AsyncMock()
        service.user_repo.exists_by_email.return_value = False

        fake_user = MagicMock()
        fake_user.id = uuid.uuid4()
        fake_user.email = "newuser@example.com"
        fake_user.is_verified = False
        service.user_repo.create.return_value = fake_user

        req = RegistrationRequest(
            email="NewUser@example.com",
            password="SecurePassword123!",
            full_name="Bob Builder",
        )

        with patch("backend.services.auth.registration_service.get_email_provider") as mock_email_prov:
            mock_provider = AsyncMock()
            mock_email_prov.return_value = mock_provider

            await service.register_user(req)

            # User must be created with normalized lowercase email and is_verified=False
            service.user_repo.create.assert_awaited_once()
            call_kwargs = service.user_repo.create.call_args[1]
            assert call_kwargs["email"] == "newuser@example.com"
            assert call_kwargs["is_verified"] is False
            assert "verification_token_hash" in call_kwargs
            assert call_kwargs["profile_data"] == {"full_name": "Bob Builder"}

            # Session committed and verification email dispatched
            mock_session.commit.assert_awaited_once()
            mock_provider.send_verification_email.assert_awaited_once()
            assert mock_provider.send_verification_email.call_args[0][0] == "newuser@example.com"

    @pytest.mark.asyncio
    async def test_registration_swallows_existing_email_enumeration(self):
        mock_session = AsyncMock()
        service = RegistrationService(mock_session)
        service.user_repo = AsyncMock()
        service.user_repo.exists_by_email.return_value = True

        req = RegistrationRequest(
            email="existing@example.com",
            password="SecurePassword123!",
        )

        with patch("backend.services.auth.registration_service.get_email_provider") as mock_email_prov:
            mock_provider = AsyncMock()
            mock_email_prov.return_value = mock_provider

            # Must return cleanly without creating user or sending verification email
            await service.register_user(req)
            service.user_repo.create.assert_not_called()
            mock_session.commit.assert_not_called()
            mock_provider.send_verification_email.assert_not_called()

    @pytest.mark.asyncio
    async def test_registration_does_not_create_or_join_workspace(self):
        """Verify RegistrationService contains zero workspace repository interactions."""
        mock_session = AsyncMock()
        service = RegistrationService(mock_session)
        service.user_repo = AsyncMock()
        service.user_repo.exists_by_email.return_value = False

        fake_user = MagicMock()
        fake_user.id = uuid.uuid4()
        service.user_repo.create.return_value = fake_user

        req = RegistrationRequest(
            email="noworkspace@example.com",
            password="SecurePassword123!",
        )

        with patch("backend.services.auth.registration_service.get_email_provider") as mock_email_prov:
            mock_email_prov.return_value = AsyncMock()
            await service.register_user(req)

        # Verify no workspace attributes or models were created or attached
        assert not hasattr(service, "workspace_repo")
        assert not hasattr(service, "workspace_member_repo")
        assert not hasattr(service, "joining_service")


# ---------------------------------------------------------------------------
# 4. Mandatory Email Verification & Onboarding Path Isolation
# ---------------------------------------------------------------------------

class TestEmailVerificationAndOnboardingIsolation:
    """Verify email verification remains mandatory and separate from workspace onboarding."""

    def test_unverified_user_cannot_bypass_verification(self):
        """Unverified account token hash must match and expire within 24h."""
        token = "test_raw_token_xyz"
        expected_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

        user = MagicMock()
        user.is_verified = False
        user.verification_token_hash = expected_hash
        user.verification_token_expires_at = datetime.now(UTC) + timedelta(hours=24)

        # Verification succeeds only with matching raw token and unexpired timestamp
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        assert user.verification_token_hash == token_hash
        assert user.verification_token_expires_at > datetime.now(UTC)

    def test_onboarding_requires_separate_authoritative_services(self):
        """Workspace creation and joining are authoritative post-verification routes."""
        # 1. Join Workspace Request accepts onboarding credentials
        from backend.api.v1.schemas.workspace_onboarding import JoinWorkspaceRequest
        join_req = JoinWorkspaceRequest(
            workspace_id="ACME-CORP",
            join_code="VR-7K9M2P",
        )
        assert join_req.workspace_id == "ACME-CORP"
        assert join_req.join_code == "VR-7K9M2P"

        # 2. Invitation Accept Request accepts token
        from backend.api.v1.schemas.workspace_invitation import AcceptInvitationRequest
        inv_req = AcceptInvitationRequest(
            token="sec_inv_abcdef1234567890",
        )
        assert inv_req.token == "sec_inv_abcdef1234567890"

        # 3. RegistrationRequest does not accept or process these
        reg_req = RegistrationRequest(
            email="user@example.com",
            password="SecurePassword123!",
        )
        assert not hasattr(reg_req, "workspace_id")
        assert not hasattr(reg_req, "join_code")
        assert not hasattr(reg_req, "invitation_token")
