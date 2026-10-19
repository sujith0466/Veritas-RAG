"""Unit tests for AUD-011: Chat Session Ownership and Strict Tenant Resolution."""

from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import json
import pytest

from backend.modules.chat.models.chat_session import ChatSession
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember
from backend.modules.chat.services.chat_orchestrator import ChatOrchestrator


@pytest.fixture
def mock_session_maker():
    session_mock = AsyncMock()
    maker = MagicMock()
    maker.return_value.__aenter__.return_value = session_mock
    maker.return_value.__aexit__.return_value = None
    return maker, session_mock


@pytest.mark.asyncio
async def test_chat_stream_mismatched_user_ownership(mock_session_maker):
    """AUD-011 Gate: If user does not own session, yield SESSION_ACCESS_DENIED."""
    maker, session_mock = mock_session_maker

    session_id = str(uuid.uuid4())
    owner_id = str(uuid.uuid4())
    attacker_id = str(uuid.uuid4())
    ws_id = str(uuid.uuid4())

    fake_session = MagicMock(spec=ChatSession)
    fake_session.id = session_id
    fake_session.user_id = owner_id
    fake_session.tenant_id = ws_id

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = fake_session
    session_mock.execute.return_value = mock_res

    orchestrator = ChatOrchestrator(ai_wrapper_service=MagicMock(), chat_repo=MagicMock())

    with patch("backend.modules.chat.services.chat_orchestrator.get_session_factory", return_value=maker):
        events = []
        async for event in orchestrator.stream_chat(
            session_id=session_id,
            tenant_id=ws_id,
            user_id=attacker_id,
            query="Hello",
            correlation_id=str(uuid.uuid4()),
        ):
            events.append(event)

        assert len(events) == 1
        assert "event: error" in events[0]
        assert "SESSION_ACCESS_DENIED" in events[0]
        assert "User does not own this chat session" in events[0]


@pytest.mark.asyncio
async def test_chat_stream_session_not_found(mock_session_maker):
    """AUD-011 Gate: If session does not exist, yield SESSION_ACCESS_DENIED."""
    maker, session_mock = mock_session_maker

    session_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    ws_id = str(uuid.uuid4())

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    session_mock.execute.return_value = mock_res

    orchestrator = ChatOrchestrator(ai_wrapper_service=MagicMock(), chat_repo=MagicMock())

    with patch("backend.modules.chat.services.chat_orchestrator.get_session_factory", return_value=maker):
        events = []
        async for event in orchestrator.stream_chat(
            session_id=session_id,
            tenant_id=ws_id,
            user_id=user_id,
            query="Hello",
            correlation_id=str(uuid.uuid4()),
        ):
            events.append(event)

        assert len(events) == 1
        assert "event: error" in events[0]
        assert "SESSION_ACCESS_DENIED" in events[0]


@pytest.mark.asyncio
async def test_chat_stream_workspace_mismatch(mock_session_maker):
    """AUD-011 Gate: If caller supplies workspace_id that differs from session workspace, yield WORKSPACE_MISMATCH."""
    maker, session_mock = mock_session_maker

    session_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    session_ws = str(uuid.uuid4())
    requested_ws = uuid.uuid4()

    fake_session = MagicMock(spec=ChatSession)
    fake_session.id = session_id
    fake_session.user_id = user_id
    fake_session.tenant_id = session_ws

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = fake_session
    session_mock.execute.return_value = mock_res

    orchestrator = ChatOrchestrator(ai_wrapper_service=MagicMock(), chat_repo=MagicMock())

    with patch("backend.modules.chat.services.chat_orchestrator.get_session_factory", return_value=maker):
        events = []
        async for event in orchestrator.stream_chat(
            session_id=session_id,
            tenant_id=session_ws,
            user_id=user_id,
            query="Hello",
            correlation_id=str(uuid.uuid4()),
            workspace_id=requested_ws,
        ):
            events.append(event)

        assert len(events) == 1
        assert "event: error" in events[0]
        assert "WORKSPACE_MISMATCH" in events[0]


@pytest.mark.asyncio
async def test_chat_stream_non_member_workspace_required(mock_session_maker):
    """AUD-011 Gate: If user is not an active member of the session's workspace, yield WORKSPACE_REQUIRED."""
    maker, session_mock = mock_session_maker

    session_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    session_ws = str(uuid.uuid4())

    fake_session = MagicMock(spec=ChatSession)
    fake_session.id = session_id
    fake_session.user_id = user_id
    fake_session.tenant_id = session_ws

    mock_session_res = MagicMock()
    mock_session_res.scalar_one_or_none.return_value = fake_session

    mock_member_res = MagicMock()
    mock_member_res.scalar_one_or_none.return_value = None  # Not an active member

    session_mock.execute.side_effect = [mock_session_res, mock_member_res]

    orchestrator = ChatOrchestrator(ai_wrapper_service=MagicMock(), chat_repo=MagicMock())

    with patch("backend.modules.chat.services.chat_orchestrator.get_session_factory", return_value=maker):
        events = []
        async for event in orchestrator.stream_chat(
            session_id=session_id,
            tenant_id=session_ws,
            user_id=user_id,
            query="Hello",
            correlation_id=str(uuid.uuid4()),
        ):
            events.append(event)

        assert len(events) == 1
        assert "event: error" in events[0]
        assert "WORKSPACE_REQUIRED" in events[0]
        assert "User is not an active member of this workspace" in events[0]
