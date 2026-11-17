"""
Veritas RAG — Section 3: Package T-3.C
Unit Test Suite: Lifecycle Admission Control & Service Mapping

Validates validate_user_admission_for_share helper and domain exception mappings
across all membership introduction and restoration paths.
"""

from datetime import datetime, timedelta, timezone
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from backend.core.security.admission import (
    UserAdmissionDeniedError,
    validate_user_admission_for_share,
)
from backend.models.entities.user import User
from backend.services.workspace.invitation_service import (
    InvitationConflictError,
    WorkspaceInvitationService,
)
from backend.services.workspace.workspace_joining_service import (
    WorkspaceJoiningService,
    WorkspaceMembershipConflictError,
)
from backend.services.workspace.access_request_service import (
    AccessRequestConflictError,
    AccessRequestService,
)
from backend.services.workspace.membership_service import (
    MembershipConflictError,
    WorkspaceMembershipService,
)


@pytest.mark.asyncio
class TestValidateUserAdmissionForShare:
    """Tests for the shared validate_user_admission_for_share helper."""

    async def test_admission_success_active_user(self):
        """Active, non-deleted user is admitted and returned."""
        session = AsyncMock()
        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            email="active@example.com",
            is_active=True,
            is_deleted=False,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user
        session.execute.return_value = mock_result

        result = await validate_user_admission_for_share(session, user_id)
        assert result is user
        assert session.execute.called

    async def test_admission_denied_user_not_found(self):
        """Non-existent user raises UserAdmissionDeniedError."""
        session = AsyncMock()
        user_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result

        with pytest.raises(UserAdmissionDeniedError, match="not found"):
            await validate_user_admission_for_share(session, user_id)

    async def test_admission_denied_user_deleted(self):
        """Soft-deleted user raises UserAdmissionDeniedError."""
        session = AsyncMock()
        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            email="deleted@example.com",
            is_active=True,
            is_deleted=True,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user
        session.execute.return_value = mock_result

        with pytest.raises(UserAdmissionDeniedError, match="inactive or deleted"):
            await validate_user_admission_for_share(session, user_id)

    async def test_admission_denied_user_inactive(self):
        """Inactive user raises UserAdmissionDeniedError."""
        session = AsyncMock()
        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            email="inactive@example.com",
            is_active=False,
            is_deleted=False,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user
        session.execute.return_value = mock_result

        with pytest.raises(UserAdmissionDeniedError, match="inactive or deleted"):
            await validate_user_admission_for_share(session, user_id)


@pytest.mark.asyncio
class TestServiceAdmissionExceptionMappings:
    """Tests that domain services map UserAdmissionDeniedError to their respective domain conflict errors."""

    async def test_invitation_service_maps_denial_to_invitation_conflict(self):
        """Invitation acceptance maps UserAdmissionDeniedError to InvitationConflictError."""
        service = WorkspaceInvitationService(
            invitation_repo=AsyncMock(),
            member_repo=AsyncMock(),
            workspace_repo=AsyncMock(),
            settings_repo=AsyncMock(),
            email_provider=AsyncMock(),
        )
        session = AsyncMock()
        user_context = MagicMock()
        user_context.id = uuid.uuid4()
        user_context.email = "test@example.com"

        invitation = MagicMock()
        invitation.status = "PENDING"
        invitation.email = "test@example.com"
        invitation.expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        invitation.workspace_id = uuid.uuid4()
        invitation.token_hash = "mock_hash"
        service.invitation_repo.get_by_token_selector_for_update = AsyncMock(return_value=invitation)
        service.invitation_repo.get_by_token_hash_for_update = AsyncMock(return_value=invitation)
        service.workspace_repo.get_by_id = AsyncMock(return_value=MagicMock(status="ACTIVE"))

        with patch("backend.services.workspace.invitation_service.verify_invitation_secret", return_value=True), \
             patch(
                "backend.core.security.admission.validate_user_admission_for_share",
                side_effect=UserAdmissionDeniedError("User account is inactive or deleted."),
             ):
            with pytest.raises(InvitationConflictError, match="inactive, deleted, or deactivating"):
                await service.accept_invitation(session, "sel:sec", user_context)

    async def test_join_via_code_maps_denial_to_membership_conflict(self):
        """Join via code maps UserAdmissionDeniedError to WorkspaceMembershipConflictError."""
        service = WorkspaceJoiningService(
            workspace_repo=AsyncMock(),
            settings_repo=AsyncMock(),
            member_repo=AsyncMock(),
            join_code_service=AsyncMock(),
            invitation_service=AsyncMock(),
        )
        session = AsyncMock()
        user_id = uuid.uuid4()

        with patch(
            "backend.core.security.admission.validate_user_admission_for_share",
            side_effect=UserAdmissionDeniedError("User account is inactive or deleted."),
        ):
            with pytest.raises(WorkspaceMembershipConflictError, match="inactive, deleted, or deactivating"):
                await service._join_via_code(session, user_id, "test@example.com", "ws-slug", "CODE123")

    async def test_join_via_open_maps_denial_to_membership_conflict(self):
        """Open join maps UserAdmissionDeniedError to WorkspaceMembershipConflictError."""
        service = WorkspaceJoiningService(
            workspace_repo=AsyncMock(),
            settings_repo=AsyncMock(),
            member_repo=AsyncMock(),
            join_code_service=AsyncMock(),
            invitation_service=AsyncMock(),
        )
        session = AsyncMock()
        user_id = uuid.uuid4()

        with patch(
            "backend.core.security.admission.validate_user_admission_for_share",
            side_effect=UserAdmissionDeniedError("User account is inactive or deleted."),
        ):
            with pytest.raises(WorkspaceMembershipConflictError, match="inactive, deleted, or deactivating"):
                await service._join_via_open(session, user_id, "test@example.com", "ws-slug")

    async def test_access_request_maps_denial_to_access_request_conflict(self):
        """Access request approval maps UserAdmissionDeniedError to AccessRequestConflictError."""
        service = AccessRequestService(
            access_repo=AsyncMock(),
            member_repo=AsyncMock(),
            workspace_repo=AsyncMock(),
        )
        session = AsyncMock()
        workspace_id = uuid.uuid4()
        actor_id = uuid.uuid4()
        request_id = uuid.uuid4()

        service._verify_actor_admin = AsyncMock()
        service.workspace_repo.get_by_id = AsyncMock(return_value=MagicMock(status="ACTIVE"))
        req = MagicMock()
        req.id = request_id
        req.workspace_id = workspace_id
        req.user_id = uuid.uuid4()
        req.request_type = "JOIN_APPROVAL"
        req.requested_role = "MEMBER"
        req.status = "PENDING"
        service.access_repo.get_by_id_for_update = AsyncMock(return_value=req)

        with patch(
            "backend.core.security.admission.validate_user_admission_for_share",
            side_effect=UserAdmissionDeniedError("User account is inactive or deleted."),
        ):
            with pytest.raises(AccessRequestConflictError, match="inactive or deleted"):
                await service.approve_request(session, workspace_id, actor_id, request_id)

    async def test_membership_restore_maps_denial_to_membership_conflict(self):
        """Membership restoration maps UserAdmissionDeniedError to MembershipConflictError (T3C-DEC-2)."""
        service = WorkspaceMembershipService(
            workspace_repo=AsyncMock(),
            member_repo=AsyncMock(),
        )
        session = AsyncMock()
        workspace_id = uuid.uuid4()
        actor_id = uuid.uuid4()
        member_id = uuid.uuid4()

        target_member = MagicMock()
        target_member.id = member_id
        target_member.user_id = uuid.uuid4()
        target_member.role = "MEMBER"
        service.member_repo.get_by_id = AsyncMock(return_value=target_member)

        with patch(
            "backend.core.security.admission.validate_user_admission_for_share",
            side_effect=UserAdmissionDeniedError("User account is inactive or deleted."),
        ):
            with pytest.raises(MembershipConflictError, match="inactive, deleted, or deactivating"):
                await service.restore_member(session, workspace_id, actor_id, member_id)
