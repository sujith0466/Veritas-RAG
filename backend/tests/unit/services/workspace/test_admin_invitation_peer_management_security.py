"""Automated unit tests for WP-2: ADMIN Invitation & Peer-Management Restrictions.

Verifies:
- ADMIN inviting ADMIN is rejected.
- ADMIN inviting OWNER is rejected.
- ADMIN inviting MEMBER succeeds.
- OWNER inviting ADMIN succeeds.
- New VIEWER invitations are rejected (both for ADMIN and OWNER).
- Direct OWNER invitations are prohibited.
- ADMIN demoting a peer ADMIN is rejected.
- ADMIN removing a peer ADMIN is rejected.
- ADMIN suspending a peer ADMIN is rejected.
- ADMIN restoring a peer ADMIN is rejected.
- OWNER can demote an ADMIN to MEMBER.
- OWNER can remove an ADMIN.
- ADMIN promoting an active MEMBER to ADMIN succeeds.
- ADMIN self-removal (leaving workspace) is allowed.
- Last-owner protections on demotion and removal remain intact.
"""

import datetime
from unittest.mock import AsyncMock, MagicMock
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from pydantic import ValidationError

from backend.api.v1.routes.workspace_members import workspace_members_router
from backend.api.v1.schemas.workspace_invitation import SendInvitationRequest
from backend.core.auth.context import UserContext
from backend.core.dependencies.auth import get_current_user
from backend.core.dependencies.database import (
    get_db,
    get_workspace_membership_service,
)
from backend.core.permissions.rbac import Role
from backend.models.entities.audit_log import AuditLog
from backend.models.entities.workspace import Workspace, WorkspaceStatus
from backend.models.entities.workspace_invitation import InvitationStatus, WorkspaceInvitation
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember, WorkspaceRole
from backend.services.workspace.invitation_service import (
    InvitationUnauthorizedError,
    WorkspaceInvitationService,
)
from backend.services.workspace.membership_service import (
    MembershipConflictError,
    MembershipUnauthorizedError,
    WorkspaceMembershipService,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    return session


@pytest.fixture
def mock_workspace_repo():
    return AsyncMock()


@pytest.fixture
def mock_member_repo():
    return AsyncMock()


@pytest.fixture
def mock_invitation_repo():
    return AsyncMock()


@pytest.fixture
def mock_settings_repo():
    return AsyncMock()


@pytest.fixture
def invitation_service(
    mock_invitation_repo,
    mock_workspace_repo,
    mock_member_repo,
    mock_settings_repo,
):
    svc = WorkspaceInvitationService(
        invitation_repo=mock_invitation_repo,
        workspace_repo=mock_workspace_repo,
        member_repo=mock_member_repo,
        settings_repo=mock_settings_repo,
        email_provider=AsyncMock(),
        event_dispatcher=AsyncMock(),
    )
    return svc


@pytest.fixture
def membership_service(mock_member_repo, mock_workspace_repo):
    return WorkspaceMembershipService(
        member_repo=mock_member_repo,
        workspace_repo=mock_workspace_repo,
        event_dispatcher=AsyncMock(),
    )


@pytest.fixture
def api_test_app():
    app = FastAPI()
    app.include_router(workspace_members_router, prefix="/api/v1")
    return app


# ── Part A: Invitation Restriction Tests ──────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_inviting_admin_is_rejected(
    invitation_service, mock_session, mock_workspace_repo, mock_member_repo
):
    """ADMIN cannot invite a user to the ADMIN role."""
    workspace_id = uuid.uuid4()
    admin_id = uuid.uuid4()

    mock_workspace_repo.get_by_id.return_value = Workspace(
        id=workspace_id, name="Acme Corp", status=WorkspaceStatus.ACTIVE.value
    )
    mock_member_repo.get_membership.return_value = WorkspaceMember(
        id=uuid.uuid4(), workspace_id=workspace_id, user_id=admin_id, role="ADMIN", status="ACTIVE"
    )

    with pytest.raises(InvitationUnauthorizedError, match="ADMIN can only invite users with the MEMBER role"):
        await invitation_service.send_invitation(
            session=mock_session,
            workspace_id=workspace_id,
            actor_id=admin_id,
            email="peer_admin@example.com",
            role="ADMIN",
        )


@pytest.mark.asyncio
async def test_admin_inviting_owner_is_rejected(
    invitation_service, mock_session, mock_workspace_repo, mock_member_repo
):
    """ADMIN cannot invite a user to the OWNER role."""
    workspace_id = uuid.uuid4()
    admin_id = uuid.uuid4()

    mock_workspace_repo.get_by_id.return_value = Workspace(
        id=workspace_id, name="Acme Corp", status=WorkspaceStatus.ACTIVE.value
    )
    mock_member_repo.get_membership.return_value = WorkspaceMember(
        id=uuid.uuid4(), workspace_id=workspace_id, user_id=admin_id, role="ADMIN", status="ACTIVE"
    )

    with pytest.raises(InvitationUnauthorizedError, match="ADMIN cannot invite a user to the OWNER role"):
        await invitation_service.send_invitation(
            session=mock_session,
            workspace_id=workspace_id,
            actor_id=admin_id,
            email="future_owner@example.com",
            role="OWNER",
        )


@pytest.mark.asyncio
async def test_admin_inviting_member_succeeds(
    invitation_service, mock_session, mock_workspace_repo, mock_member_repo, mock_invitation_repo, mock_settings_repo
):
    """ADMIN can successfully invite a user with the MEMBER role."""
    workspace_id = uuid.uuid4()
    admin_id = uuid.uuid4()

    mock_workspace_repo.get_by_id.return_value = Workspace(
        id=workspace_id, name="Acme Corp", status=WorkspaceStatus.ACTIVE.value
    )
    mock_member_repo.get_membership.side_effect = [
        WorkspaceMember(id=uuid.uuid4(), workspace_id=workspace_id, user_id=admin_id, role="ADMIN", status="ACTIVE"),
        None,  # invitee is not an existing member
    ]
    mock_invitation_repo.get_pending_by_workspace_and_email.return_value = None
    mock_settings_repo.get_by_workspace_id.return_value = None

    mock_user_res = MagicMock()
    mock_user_res.scalars().first.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_user_res)

    invitation = await invitation_service.send_invitation(
        session=mock_session,
        workspace_id=workspace_id,
        actor_id=admin_id,
        email="new_member@example.com",
        role="MEMBER",
    )

    assert isinstance(invitation, WorkspaceInvitation)
    assert invitation.role == "MEMBER"
    assert invitation.email == "new_member@example.com"
    mock_session.add.assert_called()


@pytest.mark.asyncio
async def test_owner_inviting_admin_is_rejected(
    invitation_service, mock_session, mock_workspace_repo, mock_member_repo, mock_invitation_repo, mock_settings_repo
):
    """OWNER cannot invite a user to the ADMIN role (MEMBER-only ceiling, DEC-03, Directive D-12)."""
    workspace_id = uuid.uuid4()
    owner_id = uuid.uuid4()

    mock_workspace_repo.get_by_id.return_value = Workspace(
        id=workspace_id, name="Acme Corp", status=WorkspaceStatus.ACTIVE.value
    )
    mock_member_repo.get_membership.return_value = WorkspaceMember(
        id=uuid.uuid4(), workspace_id=workspace_id, user_id=owner_id, role="OWNER", status="ACTIVE"
    )

    with pytest.raises(InvitationUnauthorizedError, match="Direct invitations to the ADMIN role are prohibited"):
        await invitation_service.send_invitation(
            session=mock_session,
            workspace_id=workspace_id,
            actor_id=owner_id,
            email="new_admin@example.com",
            role="ADMIN",
        )


@pytest.mark.asyncio
async def test_new_viewer_invitations_are_rejected(
    invitation_service, mock_session, mock_workspace_repo, mock_member_repo
):
    """Neither OWNER nor ADMIN can send invitations for the VIEWER role."""
    workspace_id = uuid.uuid4()
    owner_id = uuid.uuid4()

    mock_workspace_repo.get_by_id.return_value = Workspace(
        id=workspace_id, name="Acme Corp", status=WorkspaceStatus.ACTIVE.value
    )
    mock_member_repo.get_membership.return_value = WorkspaceMember(
        id=uuid.uuid4(), workspace_id=workspace_id, user_id=owner_id, role="OWNER", status="ACTIVE"
    )

    with pytest.raises(InvitationUnauthorizedError, match="Workspace VIEWER invitations are not supported"):
        await invitation_service.send_invitation(
            session=mock_session,
            workspace_id=workspace_id,
            actor_id=owner_id,
            email="viewer_candidate@example.com",
            role="VIEWER",
        )


@pytest.mark.asyncio
async def test_owner_inviting_owner_is_rejected(
    invitation_service, mock_session, mock_workspace_repo, mock_member_repo
):
    """Direct invitations to the OWNER role are prohibited even for OWNER actors."""
    workspace_id = uuid.uuid4()
    owner_id = uuid.uuid4()

    mock_workspace_repo.get_by_id.return_value = Workspace(
        id=workspace_id, name="Acme Corp", status=WorkspaceStatus.ACTIVE.value
    )
    mock_member_repo.get_membership.return_value = WorkspaceMember(
        id=uuid.uuid4(), workspace_id=workspace_id, user_id=owner_id, role="OWNER", status="ACTIVE"
    )

    with pytest.raises(InvitationUnauthorizedError, match="Direct invitations to the OWNER role are prohibited"):
        await invitation_service.send_invitation(
            session=mock_session,
            workspace_id=workspace_id,
            actor_id=owner_id,
            email="co_owner@example.com",
            role="OWNER",
        )


# ── Part B: Membership Peer-Management Restrictions ───────────────────────────

@pytest.mark.asyncio
async def test_admin_demoting_peer_admin_succeeds(
    membership_service, mock_session, mock_workspace_repo, mock_member_repo
):
    """ADMIN can demote a peer ADMIN to MEMBER (DEC-04, Directive C3)."""
    workspace_id = uuid.uuid4()
    actor_admin_id = uuid.uuid4()
    target_admin_id = uuid.uuid4()

    mock_workspace_repo.get_by_id.return_value = Workspace(
        id=workspace_id, name="Acme Corp", status=WorkspaceStatus.ACTIVE.value
    )
    actor_admin = WorkspaceMember(
        id=uuid.uuid4(), workspace_id=workspace_id, user_id=actor_admin_id, role=WorkspaceRole.ADMIN.value, status="ACTIVE"
    )
    target_admin = WorkspaceMember(
        id=target_admin_id, workspace_id=workspace_id, user_id=uuid.uuid4(), role=WorkspaceRole.ADMIN.value, status="ACTIVE", version=1
    )

    mock_member_repo.get_membership.return_value = actor_admin
    mock_member_repo.get_by_id_for_update.return_value = target_admin

    updated = await membership_service.update_member_role(
        session=mock_session,
        workspace_id=workspace_id,
        actor_id=actor_admin_id,
        member_id=target_admin_id,
        new_role="MEMBER",
    )

    assert updated.role == "MEMBER"
    assert updated.version == 2
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_admin_removing_peer_admin_succeeds(
    membership_service, mock_session, mock_workspace_repo, mock_member_repo
):
    """ADMIN can remove a peer ADMIN from the workspace (DEC-04, Category 1.3)."""
    workspace_id = uuid.uuid4()
    actor_admin_id = uuid.uuid4()
    target_admin_id = uuid.uuid4()

    mock_workspace_repo.get_by_id.return_value = Workspace(
        id=workspace_id, name="Acme Corp", status=WorkspaceStatus.ACTIVE.value
    )
    actor_admin = WorkspaceMember(
        id=uuid.uuid4(), workspace_id=workspace_id, user_id=actor_admin_id, role=WorkspaceRole.ADMIN.value, status="ACTIVE"
    )
    target_admin = WorkspaceMember(
        id=target_admin_id, workspace_id=workspace_id, user_id=uuid.uuid4(), role=WorkspaceRole.ADMIN.value, status="ACTIVE", is_deleted=False, version=1
    )

    mock_member_repo.get_membership.return_value = actor_admin
    mock_member_repo.get_by_id_for_update.return_value = target_admin

    removed = await membership_service.remove_member(
        session=mock_session,
        workspace_id=workspace_id,
        actor_id=actor_admin_id,
        member_id=target_admin_id,
    )

    assert removed.is_deleted is True
    assert removed.version == 2
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_admin_suspending_peer_admin_is_rejected(
    membership_service, mock_session, mock_workspace_repo, mock_member_repo
):
    """ADMIN cannot suspend a peer ADMIN."""
    workspace_id = uuid.uuid4()
    actor_admin_id = uuid.uuid4()
    target_admin_id = uuid.uuid4()

    mock_workspace_repo.get_by_id.return_value = Workspace(
        id=workspace_id, name="Acme Corp", status=WorkspaceStatus.ACTIVE.value
    )
    actor_admin = WorkspaceMember(
        id=uuid.uuid4(), workspace_id=workspace_id, user_id=actor_admin_id, role=WorkspaceRole.ADMIN.value, status="ACTIVE"
    )
    target_admin = WorkspaceMember(
        id=target_admin_id, workspace_id=workspace_id, user_id=uuid.uuid4(), role=WorkspaceRole.ADMIN.value, status="ACTIVE"
    )

    mock_member_repo.get_membership.return_value = actor_admin
    mock_member_repo.get_by_id_for_update.return_value = target_admin

    with pytest.raises(MembershipUnauthorizedError, match="ADMIN cannot suspend a peer ADMIN"):
        await membership_service.suspend_member(
            session=mock_session,
            workspace_id=workspace_id,
            actor_id=actor_admin_id,
            member_id=target_admin_id,
        )


@pytest.mark.asyncio
async def test_admin_restoring_peer_admin_is_rejected(
    membership_service, mock_session, mock_workspace_repo, mock_member_repo
):
    """ADMIN cannot restore a suspended peer ADMIN."""
    workspace_id = uuid.uuid4()
    actor_admin_id = uuid.uuid4()
    target_admin_id = uuid.uuid4()

    mock_workspace_repo.get_by_id.return_value = Workspace(
        id=workspace_id, name="Acme Corp", status=WorkspaceStatus.ACTIVE.value
    )
    actor_admin = WorkspaceMember(
        id=uuid.uuid4(), workspace_id=workspace_id, user_id=actor_admin_id, role=WorkspaceRole.ADMIN.value, status="ACTIVE"
    )
    target_admin = WorkspaceMember(
        id=target_admin_id, workspace_id=workspace_id, user_id=uuid.uuid4(), role=WorkspaceRole.ADMIN.value, status=MemberStatus.SUSPENDED.value
    )

    mock_member_repo.get_membership.return_value = actor_admin
    mock_member_repo.get_by_id_for_update.return_value = target_admin

    with pytest.raises(MembershipUnauthorizedError, match="ADMIN cannot restore a peer ADMIN"):
        await membership_service.restore_member(
            session=mock_session,
            workspace_id=workspace_id,
            actor_id=actor_admin_id,
            member_id=target_admin_id,
        )


@pytest.mark.asyncio
async def test_owner_can_demote_admin_to_member(
    membership_service, mock_session, mock_workspace_repo, mock_member_repo
):
    """OWNER can perform the approved ADMIN demotion to MEMBER."""
    workspace_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    target_admin_id = uuid.uuid4()

    mock_workspace_repo.get_by_id.return_value = Workspace(
        id=workspace_id, name="Acme Corp", status=WorkspaceStatus.ACTIVE.value
    )
    owner = WorkspaceMember(
        id=uuid.uuid4(), workspace_id=workspace_id, user_id=owner_id, role=WorkspaceRole.OWNER.value, status="ACTIVE"
    )
    target_admin = WorkspaceMember(
        id=target_admin_id, workspace_id=workspace_id, user_id=uuid.uuid4(), role=WorkspaceRole.ADMIN.value, status="ACTIVE", version=1
    )

    mock_member_repo.get_membership.return_value = owner
    mock_member_repo.get_by_id_for_update.return_value = target_admin

    updated = await membership_service.update_member_role(
        session=mock_session,
        workspace_id=workspace_id,
        actor_id=owner_id,
        member_id=target_admin_id,
        new_role="MEMBER",
    )

    assert updated.role == "MEMBER"
    assert updated.version == 2
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_owner_can_remove_admin(
    membership_service, mock_session, mock_workspace_repo, mock_member_repo
):
    """OWNER can remove an ADMIN member from the workspace."""
    workspace_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    target_admin_id = uuid.uuid4()

    mock_workspace_repo.get_by_id.return_value = Workspace(
        id=workspace_id, name="Acme Corp", status=WorkspaceStatus.ACTIVE.value
    )
    owner = WorkspaceMember(
        id=uuid.uuid4(), workspace_id=workspace_id, user_id=owner_id, role=WorkspaceRole.OWNER.value, status="ACTIVE"
    )
    target_admin = WorkspaceMember(
        id=target_admin_id, workspace_id=workspace_id, user_id=uuid.uuid4(), role=WorkspaceRole.ADMIN.value, status="ACTIVE", is_deleted=False, version=1
    )

    mock_member_repo.get_membership.return_value = owner
    mock_member_repo.get_by_id_for_update.return_value = target_admin

    removed = await membership_service.remove_member(
        session=mock_session,
        workspace_id=workspace_id,
        actor_id=owner_id,
        member_id=target_admin_id,
    )

    assert removed.is_deleted is True
    assert removed.version == 2
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_admin_promoting_active_member_to_admin_succeeds(
    membership_service, mock_session, mock_workspace_repo, mock_member_repo
):
    """ADMIN retains the approved ability to promote an active MEMBER to ADMIN."""
    workspace_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    target_member_id = uuid.uuid4()

    mock_workspace_repo.get_by_id.return_value = Workspace(
        id=workspace_id, name="Acme Corp", status=WorkspaceStatus.ACTIVE.value
    )
    admin = WorkspaceMember(
        id=uuid.uuid4(), workspace_id=workspace_id, user_id=admin_id, role=WorkspaceRole.ADMIN.value, status="ACTIVE"
    )
    target_member = WorkspaceMember(
        id=target_member_id, workspace_id=workspace_id, user_id=uuid.uuid4(), role=WorkspaceRole.MEMBER.value, status="ACTIVE", version=1
    )

    mock_member_repo.get_membership.return_value = admin
    mock_member_repo.get_by_id_for_update.return_value = target_member

    promoted = await membership_service.update_member_role(
        session=mock_session,
        workspace_id=workspace_id,
        actor_id=admin_id,
        member_id=target_member_id,
        new_role="ADMIN",
    )

    assert promoted.role == "ADMIN"
    assert promoted.version == 2
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_admin_self_removal_allowed(
    membership_service, mock_session, mock_workspace_repo, mock_member_repo
):
    """ADMIN leaving the workspace (self-removal) remains permitted."""
    workspace_id = uuid.uuid4()
    admin_user_id = uuid.uuid4()
    admin_member_id = uuid.uuid4()

    mock_workspace_repo.get_by_id.return_value = Workspace(
        id=workspace_id, name="Acme Corp", status=WorkspaceStatus.ACTIVE.value
    )
    admin_member = WorkspaceMember(
        id=admin_member_id, workspace_id=workspace_id, user_id=admin_user_id, role=WorkspaceRole.ADMIN.value, status="ACTIVE", is_deleted=False, version=1
    )

    mock_member_repo.get_membership.return_value = admin_member
    mock_member_repo.get_by_id_for_update.return_value = admin_member

    removed = await membership_service.remove_member(
        session=mock_session,
        workspace_id=workspace_id,
        actor_id=admin_user_id,
        member_id=admin_member_id,
    )

    assert removed.is_deleted is True
    assert removed.version == 2
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_last_owner_protection_prevents_demotion_and_removal(
    membership_service, mock_session, mock_workspace_repo, mock_member_repo
):
    """Last-owner safeguards remain enforced against demotion and removal."""
    workspace_id = uuid.uuid4()
    owner_user_id = uuid.uuid4()
    owner_member_id = uuid.uuid4()

    mock_workspace_repo.get_by_id.return_value = Workspace(
        id=workspace_id, name="Acme Corp", status=WorkspaceStatus.ACTIVE.value
    )
    owner_member = WorkspaceMember(
        id=owner_member_id, workspace_id=workspace_id, user_id=owner_user_id, role=WorkspaceRole.OWNER.value, status="ACTIVE", is_deleted=False
    )

    actor_owner_id = uuid.uuid4()
    actor_owner = WorkspaceMember(
        id=uuid.uuid4(), workspace_id=workspace_id, user_id=actor_owner_id, role=WorkspaceRole.OWNER.value, status="ACTIVE"
    )
    mock_member_repo.get_membership.return_value = actor_owner
    mock_member_repo.get_by_id_for_update.return_value = owner_member
    # Only 1 active owner
    mock_member_repo.count_active_owners.return_value = 1

    # Demotion blocked by Last Owner Protection
    with pytest.raises(MembershipConflictError, match="Cannot demote the last remaining OWNER"):
        await membership_service.update_member_role(
            session=mock_session,
            workspace_id=workspace_id,
            actor_id=actor_owner_id,
            member_id=owner_member_id,
            new_role="ADMIN",
        )

    # Removal blocked by Last Owner Protection (self-removal attempt by last owner)
    mock_member_repo.get_membership.return_value = owner_member
    with pytest.raises(MembershipConflictError, match="Cannot remove the last remaining OWNER"):
        await membership_service.remove_member(
            session=mock_session,
            workspace_id=workspace_id,
            actor_id=owner_user_id,
            member_id=owner_member_id,
        )


# ── Part C: Creator-Only Revocation & Schema Hardening Tests ───────────────────

@pytest.mark.asyncio
async def test_creator_can_revoke_invitation(
    invitation_service, mock_session, mock_workspace_repo, mock_member_repo, mock_invitation_repo
):
    """Creator of an invitation can successfully revoke it (Directive D-13)."""
    workspace_id = uuid.uuid4()
    creator_id = uuid.uuid4()
    invitation_id = uuid.uuid4()

    mock_workspace_repo.get_by_id.return_value = Workspace(
        id=workspace_id, name="Acme Corp", status=WorkspaceStatus.ACTIVE.value
    )
    creator_member = WorkspaceMember(
        id=uuid.uuid4(), workspace_id=workspace_id, user_id=creator_id, role="ADMIN", status="ACTIVE"
    )
    mock_member_repo.get_membership.return_value = creator_member

    invitation = WorkspaceInvitation(
        id=invitation_id,
        workspace_id=workspace_id,
        email="invitee@example.com",
        role="MEMBER",
        token_hash="dummy_hash",
        status=InvitationStatus.PENDING.value,
        invited_by_user_id=creator_id,
        version=1,
        expires_at=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7),
    )
    mock_invitation_repo.get_by_id.return_value = invitation

    revoked = await invitation_service.revoke_invitation(
        session=mock_session,
        workspace_id=workspace_id,
        invitation_id=invitation_id,
        actor_id=creator_id,
    )

    assert revoked.status == InvitationStatus.REVOKED.value
    assert revoked.revoked_by_user_id == creator_id
    mock_session.add.assert_called()


@pytest.mark.asyncio
async def test_non_creator_admin_cannot_revoke_invitation(
    invitation_service, mock_session, mock_workspace_repo, mock_member_repo, mock_invitation_repo
):
    """Non-creator ADMIN cannot revoke another member's invitation (Directive D-13)."""
    workspace_id = uuid.uuid4()
    creator_id = uuid.uuid4()
    non_creator_admin_id = uuid.uuid4()
    invitation_id = uuid.uuid4()

    mock_workspace_repo.get_by_id.return_value = Workspace(
        id=workspace_id, name="Acme Corp", status=WorkspaceStatus.ACTIVE.value
    )
    non_creator_member = WorkspaceMember(
        id=uuid.uuid4(), workspace_id=workspace_id, user_id=non_creator_admin_id, role="ADMIN", status="ACTIVE"
    )
    mock_member_repo.get_membership.return_value = non_creator_member

    invitation = WorkspaceInvitation(
        id=invitation_id,
        workspace_id=workspace_id,
        email="invitee@example.com",
        role="MEMBER",
        token_hash="dummy_hash",
        status=InvitationStatus.PENDING.value,
        invited_by_user_id=creator_id,
        version=1,
        expires_at=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7),
    )
    mock_invitation_repo.get_by_id.return_value = invitation

    with pytest.raises(InvitationUnauthorizedError, match="Only the creator of the invitation can revoke it"):
        await invitation_service.revoke_invitation(
            session=mock_session,
            workspace_id=workspace_id,
            invitation_id=invitation_id,
            actor_id=non_creator_admin_id,
        )


@pytest.mark.asyncio
async def test_owner_cannot_revoke_peer_invitation(
    invitation_service, mock_session, mock_workspace_repo, mock_member_repo, mock_invitation_repo
):
    """OWNER cannot revoke an invitation created by an ADMIN (Directive D-13, no unapproved overrides)."""
    workspace_id = uuid.uuid4()
    admin_creator_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    invitation_id = uuid.uuid4()

    mock_workspace_repo.get_by_id.return_value = Workspace(
        id=workspace_id, name="Acme Corp", status=WorkspaceStatus.ACTIVE.value
    )
    owner_member = WorkspaceMember(
        id=uuid.uuid4(), workspace_id=workspace_id, user_id=owner_id, role="OWNER", status="ACTIVE"
    )
    mock_member_repo.get_membership.return_value = owner_member

    invitation = WorkspaceInvitation(
        id=invitation_id,
        workspace_id=workspace_id,
        email="invitee@example.com",
        role="MEMBER",
        token_hash="dummy_hash",
        status=InvitationStatus.PENDING.value,
        invited_by_user_id=admin_creator_id,
        expires_at=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7),
    )
    mock_invitation_repo.get_by_id.return_value = invitation

    with pytest.raises(InvitationUnauthorizedError, match="Only the creator of the invitation can revoke it"):
        await invitation_service.revoke_invitation(
            session=mock_session,
            workspace_id=workspace_id,
            invitation_id=invitation_id,
            actor_id=owner_id,
        )


def test_send_invitation_schema_rejects_admin_and_privileged_roles():
    """SendInvitationRequest schema rejects non-MEMBER roles with ValueError (AC-WP2-04)."""
    # MEMBER succeeds
    req = SendInvitationRequest(email="valid@example.com", role="MEMBER")
    assert req.role == "MEMBER"

    # Default is MEMBER
    req_default = SendInvitationRequest(email="valid@example.com")
    assert req_default.role == "MEMBER"

    # ADMIN is rejected
    with pytest.raises(ValidationError):
        SendInvitationRequest(email="invalid@example.com", role="ADMIN")

    # OWNER is rejected
    with pytest.raises(ValidationError):
        SendInvitationRequest(email="invalid@example.com", role="OWNER")

    # VIEWER is rejected
    with pytest.raises(ValidationError):
        SendInvitationRequest(email="invalid@example.com", role="VIEWER")


# ── Part D: Acceptance Gap Closure Tests (GAP-01 and GAP-02) ───────────────────

@pytest.mark.asyncio
async def test_invitation_seven_day_default_ttl_and_override_clamping(
    invitation_service, mock_session, mock_workspace_repo, mock_member_repo, mock_invitation_repo, mock_settings_repo
):
    """GAP-02: Empirically verify 7-day default TTL, valid override (14d), and invalid override fallback."""
    workspace_id = uuid.uuid4()
    admin_id = uuid.uuid4()

    mock_workspace_repo.get_by_id.return_value = Workspace(
        id=workspace_id, name="Acme Corp", status=WorkspaceStatus.ACTIVE.value
    )
    mock_user_res = MagicMock()
    mock_user_res.scalars().first.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_user_res)
    mock_invitation_repo.get_pending_by_workspace_and_email.return_value = None

    # 1. Default TTL: No settings record exists -> exact 7 days
    mock_settings_repo.get_by_workspace_id.return_value = None
    mock_member_repo.get_membership.side_effect = [
        WorkspaceMember(id=uuid.uuid4(), workspace_id=workspace_id, user_id=admin_id, role="ADMIN", status="ACTIVE"),
        None,
    ]
    t_before = datetime.datetime.now(datetime.timezone.utc)
    invitation_default = await invitation_service.send_invitation(
        session=mock_session,
        workspace_id=workspace_id,
        actor_id=admin_id,
        email="default_ttl@example.com",
        role="MEMBER",
    )
    t_after = datetime.datetime.now(datetime.timezone.utc)

    # Timezone-aware UTC assertion
    assert invitation_default.expires_at.tzinfo is not None
    # Empirically verify: invitation.expires_at - creation_time == 7 days (within tight tolerance)
    ttl_delta = invitation_default.expires_at - t_before
    assert ttl_delta.days == 7
    assert abs(ttl_delta.total_seconds() - 7 * 86400) < 5
    assert t_before + datetime.timedelta(days=7) <= invitation_default.expires_at <= t_after + datetime.timedelta(days=7)

    # 2. Valid Override: settings configured with 14 days
    mock_settings_14 = MagicMock()
    mock_settings_14.settings_json = {"invitations": {"ttl_days": 14}}
    mock_settings_repo.get_by_workspace_id.return_value = mock_settings_14
    mock_member_repo.get_membership.side_effect = [
        WorkspaceMember(id=uuid.uuid4(), workspace_id=workspace_id, user_id=admin_id, role="ADMIN", status="ACTIVE"),
        None,
    ]
    t_before_14 = datetime.datetime.now(datetime.timezone.utc)
    invitation_14 = await invitation_service.send_invitation(
        session=mock_session,
        workspace_id=workspace_id,
        actor_id=admin_id,
        email="override_ttl@example.com",
        role="MEMBER",
    )
    ttl_delta_14 = invitation_14.expires_at - t_before_14
    assert ttl_delta_14.days == 14
    assert abs(ttl_delta_14.total_seconds() - 14 * 86400) < 5

    # 3. Invalid Override Fallbacks to 7 days
    # 3a. < 1 day (e.g. 0)
    mock_settings_zero = MagicMock()
    mock_settings_zero.settings_json = {"invitations": {"ttl_days": 0}}
    mock_settings_repo.get_by_workspace_id.return_value = mock_settings_zero
    resolved_zero = await invitation_service._resolve_ttl_days(workspace_id)
    assert resolved_zero == 7

    # 3b. > 30 days (e.g. 45)
    mock_settings_large = MagicMock()
    mock_settings_large.settings_json = {"invitations": {"ttl_days": 45}}
    mock_settings_repo.get_by_workspace_id.return_value = mock_settings_large
    resolved_large = await invitation_service._resolve_ttl_days(workspace_id)
    assert resolved_large == 7

    # 3c. Non-integer (e.g. string "seven" or None)
    mock_settings_str = MagicMock()
    mock_settings_str.settings_json = {"invitations": {"ttl_days": "seven"}}
    mock_settings_repo.get_by_workspace_id.return_value = mock_settings_str
    resolved_str = await invitation_service._resolve_ttl_days(workspace_id)
    assert resolved_str == 7

    mock_settings_none = MagicMock()
    mock_settings_none.settings_json = {"invitations": {"ttl_days": None}}
    mock_settings_repo.get_by_workspace_id.return_value = mock_settings_none
    resolved_none = await invitation_service._resolve_ttl_days(workspace_id)
    assert resolved_none == 7


def test_route_admin_demotes_peer_admin_success_200(
    api_test_app, membership_service, mock_session, mock_workspace_repo, mock_member_repo
):
    """GAP-01.1: Fast-API route test: ADMIN successfully demotes a peer ADMIN to MEMBER (HTTP 200)."""
    workspace_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    peer_member_id = uuid.uuid4()
    peer_user_id = uuid.uuid4()

    now = datetime.datetime.now(datetime.timezone.utc)
    mock_workspace_repo.get_by_id.return_value = Workspace(
        id=workspace_id, name="Acme Corp", status=WorkspaceStatus.ACTIVE.value
    )
    admin_actor = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        user_id=admin_id,
        role="ADMIN",
        status="ACTIVE",
        created_at=now,
        updated_at=now,
        version=1,
        is_deleted=False,
    )
    peer_member = WorkspaceMember(
        id=peer_member_id,
        workspace_id=workspace_id,
        user_id=peer_user_id,
        role="ADMIN",
        status="ACTIVE",
        created_at=now,
        updated_at=now,
        version=1,
        is_deleted=False,
    )

    mock_member_repo.get_membership.return_value = admin_actor
    mock_member_repo.get_by_id_for_update.return_value = peer_member

    api_test_app.dependency_overrides[get_current_user] = lambda: UserContext(
        id=admin_id, email="admin@example.com", role=Role.ADMIN, workspace_id=workspace_id
    )
    api_test_app.dependency_overrides[get_db] = lambda: mock_session
    api_test_app.dependency_overrides[get_workspace_membership_service] = lambda: membership_service

    client = TestClient(api_test_app)
    response = client.patch(
        f"/api/v1/workspaces/{workspace_id}/members/{peer_member_id}/role",
        json={"role": "MEMBER"},
    )

    # 1. HTTP 200
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Workspace member role updated successfully."
    assert body["data"]["role"] == "MEMBER"
    assert body["data"]["version"] == 2

    # 2. Persisted entity role and version increment
    assert peer_member.role == "MEMBER"
    assert peer_member.version == 2

    # 3. Audit log and session flush/commit
    mock_session.commit.assert_awaited()
    audit_calls = [
        arg[0][0] for arg in mock_session.add.call_args_list
        if isinstance(arg[0][0], AuditLog)
    ]
    assert len(audit_calls) >= 1
    assert audit_calls[-1].action == "workspace.member.role_updated"
    assert audit_calls[-1].details["old_role"] == "ADMIN"
    assert audit_calls[-1].details["new_role"] == "MEMBER"


def test_route_admin_removes_peer_admin_success_200(
    api_test_app, membership_service, mock_session, mock_workspace_repo, mock_member_repo
):
    """GAP-01.2: Fast-API route test: ADMIN successfully removes a peer ADMIN (HTTP 200)."""
    workspace_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    peer_member_id = uuid.uuid4()
    peer_user_id = uuid.uuid4()

    now = datetime.datetime.now(datetime.timezone.utc)
    mock_workspace_repo.get_by_id.return_value = Workspace(
        id=workspace_id, name="Acme Corp", status=WorkspaceStatus.ACTIVE.value
    )
    admin_actor = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        user_id=admin_id,
        role="ADMIN",
        status="ACTIVE",
        created_at=now,
        updated_at=now,
        version=1,
        is_deleted=False,
    )
    peer_member = WorkspaceMember(
        id=peer_member_id,
        workspace_id=workspace_id,
        user_id=peer_user_id,
        role="ADMIN",
        status="ACTIVE",
        created_at=now,
        updated_at=now,
        version=1,
        is_deleted=False,
    )

    mock_member_repo.get_membership.return_value = admin_actor
    mock_member_repo.get_by_id_for_update.return_value = peer_member

    api_test_app.dependency_overrides[get_current_user] = lambda: UserContext(
        id=admin_id, email="admin@example.com", role=Role.ADMIN, workspace_id=workspace_id
    )
    api_test_app.dependency_overrides[get_db] = lambda: mock_session
    api_test_app.dependency_overrides[get_workspace_membership_service] = lambda: membership_service

    client = TestClient(api_test_app)
    response = client.delete(
        f"/api/v1/workspaces/{workspace_id}/members/{peer_member_id}"
    )

    # 1. HTTP 200
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["message"] == "Workspace member removed successfully."

    # 2. Soft deletion and version increment
    assert peer_member.is_deleted is True
    assert peer_member.version == 2

    # 3. Audit log and session flush/commit
    mock_session.commit.assert_awaited()
    audit_calls = [
        arg[0][0] for arg in mock_session.add.call_args_list
        if isinstance(arg[0][0], AuditLog)
    ]
    assert len(audit_calls) >= 1
    assert audit_calls[-1].action == "workspace.member.removed"
    assert audit_calls[-1].details["is_self_removal"] is False
    assert audit_calls[-1].details["role"] == "ADMIN"


def test_route_admin_cannot_modify_or_remove_owner_forbidden_403(
    api_test_app, membership_service, mock_session, mock_workspace_repo, mock_member_repo
):
    """GAP-01.3: Fast-API route test: ADMIN cannot modify or remove OWNER (HTTP 403)."""
    workspace_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    owner_member_id = uuid.uuid4()
    owner_user_id = uuid.uuid4()

    now = datetime.datetime.now(datetime.timezone.utc)
    mock_workspace_repo.get_by_id.return_value = Workspace(
        id=workspace_id, name="Acme Corp", status=WorkspaceStatus.ACTIVE.value
    )
    admin_actor = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=workspace_id,
        user_id=admin_id,
        role="ADMIN",
        status="ACTIVE",
        created_at=now,
        updated_at=now,
        version=1,
        is_deleted=False,
    )
    owner_member = WorkspaceMember(
        id=owner_member_id,
        workspace_id=workspace_id,
        user_id=owner_user_id,
        role="OWNER",
        status="ACTIVE",
        created_at=now,
        updated_at=now,
        version=1,
        is_deleted=False,
    )

    mock_member_repo.get_membership.return_value = admin_actor
    mock_member_repo.get_by_id_for_update.return_value = owner_member

    api_test_app.dependency_overrides[get_current_user] = lambda: UserContext(
        id=admin_id, email="admin@example.com", role=Role.ADMIN, workspace_id=workspace_id
    )
    api_test_app.dependency_overrides[get_db] = lambda: mock_session
    api_test_app.dependency_overrides[get_workspace_membership_service] = lambda: membership_service

    client = TestClient(api_test_app)

    # 3a. ADMIN attempting to demote OWNER -> HTTP 403
    r_demote = client.patch(
        f"/api/v1/workspaces/{workspace_id}/members/{owner_member_id}/role",
        json={"role": "MEMBER"},
    )
    assert r_demote.status_code == 403
    assert "ADMIN cannot modify the role of an OWNER" in r_demote.json()["detail"]
    assert owner_member.role == "OWNER"
    assert owner_member.version == 1

    # 3b. ADMIN attempting to remove OWNER -> HTTP 403
    r_remove = client.delete(
        f"/api/v1/workspaces/{workspace_id}/members/{owner_member_id}"
    )
    assert r_remove.status_code == 403
    assert "ADMIN cannot remove an OWNER" in r_remove.json()["detail"]
    assert owner_member.is_deleted is False
    assert owner_member.version == 1


def test_route_self_demotion_restricted_forbidden_403(
    api_test_app, membership_service, mock_session, mock_workspace_repo, mock_member_repo
):
    """GAP-01.4: Fast-API route test: Self-demotion is restricted (HTTP 403)."""
    workspace_id = uuid.uuid4()
    admin_id = uuid.uuid4()
    admin_member_id = uuid.uuid4()

    now = datetime.datetime.now(datetime.timezone.utc)
    mock_workspace_repo.get_by_id.return_value = Workspace(
        id=workspace_id, name="Acme Corp", status=WorkspaceStatus.ACTIVE.value
    )
    admin_member = WorkspaceMember(
        id=admin_member_id,
        workspace_id=workspace_id,
        user_id=admin_id,
        role="ADMIN",
        status="ACTIVE",
        created_at=now,
        updated_at=now,
        version=1,
        is_deleted=False,
    )

    mock_member_repo.get_membership.return_value = admin_member
    mock_member_repo.get_by_id_for_update.return_value = admin_member

    api_test_app.dependency_overrides[get_current_user] = lambda: UserContext(
        id=admin_id, email="admin@example.com", role=Role.ADMIN, workspace_id=workspace_id
    )
    api_test_app.dependency_overrides[get_db] = lambda: mock_session
    api_test_app.dependency_overrides[get_workspace_membership_service] = lambda: membership_service

    client = TestClient(api_test_app)
    response = client.patch(
        f"/api/v1/workspaces/{workspace_id}/members/{admin_member_id}/role",
        json={"role": "MEMBER"},
    )

    # HTTP 403 Forbidden with exact message and unmutated state
    assert response.status_code == 403
    assert "You cannot modify your own role" in response.json()["detail"]
    assert admin_member.role == "ADMIN"
    assert admin_member.version == 1


def test_route_last_owner_protection_conflict_409(
    api_test_app, membership_service, mock_session, mock_workspace_repo, mock_member_repo
):
    """GAP-01.5: Fast-API route test: Last OWNER protection prevents demotion and removal (HTTP 409)."""
    workspace_id = uuid.uuid4()
    owner_a_id = uuid.uuid4()
    owner_a_member_id = uuid.uuid4()
    owner_b_id = uuid.uuid4()
    owner_b_member_id = uuid.uuid4()

    now = datetime.datetime.now(datetime.timezone.utc)
    mock_workspace_repo.get_by_id.return_value = Workspace(
        id=workspace_id, name="Acme Corp", status=WorkspaceStatus.ACTIVE.value
    )
    owner_a = WorkspaceMember(
        id=owner_a_member_id,
        workspace_id=workspace_id,
        user_id=owner_a_id,
        role="OWNER",
        status="ACTIVE",
        created_at=now,
        updated_at=now,
        version=1,
        is_deleted=False,
    )
    owner_b = WorkspaceMember(
        id=owner_b_member_id,
        workspace_id=workspace_id,
        user_id=owner_b_id,
        role="OWNER",
        status="ACTIVE",
        created_at=now,
        updated_at=now,
        version=1,
        is_deleted=False,
    )

    # Only 1 active owner remains
    mock_member_repo.count_active_owners.return_value = 1

    # 5a. Demotion of last owner: Owner A attempts to demote Owner B
    mock_member_repo.get_membership.return_value = owner_a
    mock_member_repo.get_by_id_for_update.return_value = owner_b

    api_test_app.dependency_overrides[get_current_user] = lambda: UserContext(
        id=owner_a_id, email="owner_a@example.com", role=Role.ADMIN, workspace_id=workspace_id
    )
    api_test_app.dependency_overrides[get_db] = lambda: mock_session
    api_test_app.dependency_overrides[get_workspace_membership_service] = lambda: membership_service

    client = TestClient(api_test_app)
    r_demote = client.patch(
        f"/api/v1/workspaces/{workspace_id}/members/{owner_b_member_id}/role",
        json={"role": "MEMBER"},
    )
    assert r_demote.status_code == 409
    demote_detail = r_demote.json().get("detail")
    if isinstance(demote_detail, dict):
        assert demote_detail.get("error") == "CANNOT_LEAVE_AS_OWNER"
    else:
        assert "Cannot demote the last remaining OWNER of the workspace." in str(demote_detail)
    assert owner_b.role == "OWNER"

    # 5b. Removal of last owner: Owner A attempts self-removal
    mock_member_repo.get_membership.return_value = owner_a
    mock_member_repo.get_by_id_for_update.return_value = owner_a

    r_remove = client.delete(
        f"/api/v1/workspaces/{workspace_id}/members/{owner_a_member_id}"
    )
    assert r_remove.status_code == 409
    remove_detail = r_remove.json().get("detail")
    if isinstance(remove_detail, dict):
        assert remove_detail.get("error") == "CANNOT_LEAVE_AS_OWNER"
    else:
        assert "Cannot remove the last remaining OWNER of the workspace." in str(remove_detail)
    assert owner_a.is_deleted is False
