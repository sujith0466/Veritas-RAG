"""Unit tests for WS-B4: Member Lifecycle & Session Revocation."""

import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from backend.core.events.dispatcher import EventDispatcher
from backend.core.events.types import EventType
from backend.core.exceptions.auth import InvalidTokenException
from backend.core.security.jwt import JWTService
from backend.models.entities.workspace import Workspace, WorkspaceStatus
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember, WorkspaceRole
from backend.services.workspace.events import (
    WorkspaceMemberRemovedEvent,
    WorkspaceMemberRestoredEvent,
    WorkspaceMemberRoleUpdatedEvent,
    WorkspaceMemberSuspendedEvent,
)
from backend.services.workspace.handlers import (
    handle_member_removed,
    handle_member_role_updated,
    handle_member_suspended,
    register_workspace_event_handlers,
)
from backend.services.workspace.membership_service import (
    MembershipConflictError,
    MembershipUnauthorizedError,
    WorkspaceMembershipService,
)


@pytest.mark.asyncio
async def test_event_handler_subscribes_member_suspended():
    """Verify register_workspace_event_handlers registers WORKSPACE_MEMBER_SUSPENDED."""
    dispatcher = MagicMock(spec=EventDispatcher)
    with patch("backend.services.workspace.handlers.get_dispatcher", return_value=dispatcher):
        register_workspace_event_handlers()

    calls = dispatcher.subscribe.call_args_list
    registered_events = {call[0][0]: call[0][1] for call in calls}

    assert EventType.WORKSPACE_MEMBER_SUSPENDED in registered_events
    assert registered_events[EventType.WORKSPACE_MEMBER_SUSPENDED] == handle_member_suspended
    assert EventType.WORKSPACE_MEMBER_ROLE_UPDATED in registered_events
    assert EventType.WORKSPACE_MEMBER_REMOVED in registered_events


@pytest.mark.asyncio
async def test_handle_member_suspended_revokes_workspace_tokens():
    """Verify handle_member_suspended invokes jwt_service.revoke_user_workspace_tokens."""
    jwt_mock = MagicMock()
    jwt_mock.revoke_user_workspace_tokens = AsyncMock()

    event = WorkspaceMemberSuspendedEvent(
        workspace_id=str(uuid.uuid4()),
        member_id=str(uuid.uuid4()),
        user_id=str(uuid.uuid4()),
        actor_id=str(uuid.uuid4()),
    )

    with patch("backend.services.workspace.handlers.get_jwt_service", return_value=jwt_mock):
        await handle_member_suspended(event)

    jwt_mock.revoke_user_workspace_tokens.assert_awaited_once_with(event.user_id, event.workspace_id)


@pytest.mark.asyncio
async def test_token_invalidation_after_workspace_revocation():
    """Verify that a token with iat <= invalid_before raises InvalidTokenException."""
    redis_mock = AsyncMock()
    jwt_service = JWTService()
    jwt_service.redis = redis_mock

    user_id = str(uuid.uuid4())
    workspace_id = str(uuid.uuid4())
    other_workspace_id = str(uuid.uuid4())

    revocation_time = int(time.time())

    # Redis returns revocation_time for the suspended workspace
    async def fake_get(key: str):
        if key == f"auth:user:{user_id}:workspace:{workspace_id}:invalid_before":
            return str(revocation_time)
        return None

    redis_mock.get = AsyncMock(side_effect=fake_get)

    # 1. Stale token issued prior to revocation
    stale_payload = {
        "sub": user_id,
        "workspace_id": workspace_id,
        "iat": revocation_time - 10,
        "exp": revocation_time + 900,
        "role": "member",
        "jti": str(uuid.uuid4()),
    }
    with patch("backend.core.security.jwt.jwt.decode", return_value=stale_payload):
        with pytest.raises(InvalidTokenException, match="Token revoked"):
            await jwt_service.verify_token("stale_token_string")

    # 2. Token issued for DIFFERENT workspace is NOT revoked (isolation)
    other_payload = {
        "sub": user_id,
        "workspace_id": other_workspace_id,
        "iat": revocation_time - 10,
        "exp": revocation_time + 900,
        "role": "member",
        "jti": str(uuid.uuid4()),
    }
    with patch("backend.core.security.jwt.jwt.decode", return_value=other_payload):
        result = await jwt_service.verify_token("other_workspace_token")
        assert result.workspace_id == other_workspace_id
        assert result.sub == user_id


@pytest.mark.asyncio
async def test_suspend_member_service_flow():
    """Verify suspend_member updates DB, creates audit log, and publishes event."""
    ws_id = uuid.uuid4()
    owner_actor_id = uuid.uuid4()
    target_member_id = uuid.uuid4()
    target_user_id = uuid.uuid4()

    member_repo = MagicMock()
    workspace_repo = MagicMock()
    event_dispatcher = MagicMock()
    event_dispatcher.publish = AsyncMock()

    service = WorkspaceMembershipService(
        member_repo=member_repo,
        workspace_repo=workspace_repo,
        event_dispatcher=event_dispatcher,
    )

    workspace = Workspace(id=ws_id, name="Test WS", slug="test-ws", status=WorkspaceStatus.ACTIVE.value)
    workspace_repo.get_by_id = AsyncMock(return_value=workspace)

    owner_actor = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=owner_actor_id,
        role=WorkspaceRole.OWNER.value,
        status=MemberStatus.ACTIVE.value,
    )
    target_member = WorkspaceMember(
        id=target_member_id,
        workspace_id=ws_id,
        user_id=target_user_id,
        role=WorkspaceRole.MEMBER.value,
        status=MemberStatus.ACTIVE.value,
        version=1,
    )

    member_repo.get_membership = AsyncMock(return_value=owner_actor)
    member_repo.get_by_id_for_update = AsyncMock(return_value=target_member)

    session = AsyncMock()

    suspended = await service.suspend_member(
        session=session,
        workspace_id=ws_id,
        actor_id=owner_actor_id,
        member_id=target_member_id,
    )

    assert suspended.status == MemberStatus.SUSPENDED.value
    assert suspended.version == 2
    session.commit.assert_awaited_once()

    event_dispatcher.publish.assert_awaited_once()
    event = event_dispatcher.publish.call_args[0][0]
    assert isinstance(event, WorkspaceMemberSuspendedEvent)
    assert event.workspace_id == str(ws_id)
    assert event.member_id == str(target_member_id)
    assert event.user_id == str(target_user_id)


@pytest.mark.asyncio
async def test_restore_member_service_flow():
    """Verify restore_member updates status to ACTIVE, creates audit log, and publishes event."""
    ws_id = uuid.uuid4()
    owner_actor_id = uuid.uuid4()
    target_member_id = uuid.uuid4()
    target_user_id = uuid.uuid4()

    member_repo = MagicMock()
    workspace_repo = MagicMock()
    event_dispatcher = MagicMock()
    event_dispatcher.publish = AsyncMock()

    service = WorkspaceMembershipService(
        member_repo=member_repo,
        workspace_repo=workspace_repo,
        event_dispatcher=event_dispatcher,
    )

    workspace = Workspace(id=ws_id, name="Test WS", slug="test-ws", status=WorkspaceStatus.ACTIVE.value)
    workspace_repo.get_by_id = AsyncMock(return_value=workspace)

    owner_actor = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        user_id=owner_actor_id,
        role=WorkspaceRole.OWNER.value,
        status=MemberStatus.ACTIVE.value,
    )
    target_member = WorkspaceMember(
        id=target_member_id,
        workspace_id=ws_id,
        user_id=target_user_id,
        role=WorkspaceRole.MEMBER.value,
        status=MemberStatus.SUSPENDED.value,
        version=2,
    )

    member_repo.get_membership = AsyncMock(return_value=owner_actor)
    member_repo.get_by_id_for_update = AsyncMock(return_value=target_member)

    session = AsyncMock()

    restored = await service.restore_member(
        session=session,
        workspace_id=ws_id,
        actor_id=owner_actor_id,
        member_id=target_member_id,
    )

    assert restored.status == MemberStatus.ACTIVE.value
    assert restored.version == 3
    session.commit.assert_awaited_once()

    event_dispatcher.publish.assert_awaited_once()
    event = event_dispatcher.publish.call_args[0][0]
    assert isinstance(event, WorkspaceMemberRestoredEvent)
    assert event.workspace_id == str(ws_id)
    assert event.user_id == str(target_user_id)
