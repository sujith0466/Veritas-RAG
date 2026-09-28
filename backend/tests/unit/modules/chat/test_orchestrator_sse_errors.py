"""Unit tests for ChatOrchestrator canonical SSE error handling and metric lifecycle.

Covers CHAT-002 remediation.
"""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi import HTTPException

from backend.modules.chat.services.chat_orchestrator import ChatOrchestrator


@pytest.mark.asyncio
async def test_session_not_found_emits_canonical_sse_error():
    """Test that HTTPException(404) during session initialization emits canonical SSE error."""
    mock_ai_wrapper = MagicMock()
    mock_repo = MagicMock()
    mock_repo.list_messages = AsyncMock(return_value=[])
    mock_repo.add_message = AsyncMock(
        side_effect=HTTPException(status_code=404, detail="Chat session not found or access denied.")
    )

    orchestrator = ChatOrchestrator(chat_repo=mock_repo, ai_wrapper_service=mock_ai_wrapper)

    session_id = str(uuid.uuid4())
    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    correlation_id = str(uuid.uuid4())
    workspace_id = uuid.uuid4()

    with patch("backend.modules.chat.services.chat_orchestrator.get_session_factory") as mock_factory, \
         patch("backend.modules.chat.services.chat_orchestrator.ChatRepository", return_value=mock_repo), \
         patch("backend.modules.chat.services.chat_orchestrator.get_redis_client") as mock_redis:

        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_factory.return_value = MagicMock(return_value=mock_session)

        events = []
        async for sse_event in orchestrator.stream_chat(
            session_id=session_id,
            tenant_id=tenant_id,
            user_id=user_id,
            query="Hello",
            correlation_id=correlation_id,
            workspace_id=workspace_id,
        ):
            events.append(sse_event)

        assert len(events) == 1
        raw_sse = events[0]

        # Verify wire format
        assert "event: error\n" in raw_sse
        assert "data: {" in raw_sse

        # Parse data JSON
        for line in raw_sse.split("\n"):
            if line.startswith("data: "):
                data = json.loads(line[6:])
                assert data["code"] == "SESSION_NOT_FOUND"
                assert "Chat session not found" in data["message"]
                assert data["correlation_id"] == correlation_id
                assert data["recoverable"] is False


@pytest.mark.asyncio
async def test_session_unauthorized_emits_canonical_sse_error():
    """Test that HTTPException(403) during session initialization emits canonical UNAUTHORIZED error."""
    mock_ai_wrapper = MagicMock()
    mock_repo = MagicMock()
    mock_repo.list_messages = AsyncMock(return_value=[])
    mock_repo.add_message = AsyncMock(
        side_effect=HTTPException(status_code=403, detail="Active workspace required.")
    )

    orchestrator = ChatOrchestrator(chat_repo=mock_repo, ai_wrapper_service=mock_ai_wrapper)

    session_id = str(uuid.uuid4())
    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    correlation_id = str(uuid.uuid4())
    workspace_id = uuid.uuid4()

    with patch("backend.modules.chat.services.chat_orchestrator.get_session_factory") as mock_factory, \
         patch("backend.modules.chat.services.chat_orchestrator.ChatRepository", return_value=mock_repo), \
         patch("backend.modules.chat.services.chat_orchestrator.get_redis_client") as mock_redis:

        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_factory.return_value = MagicMock(return_value=mock_session)

        events = []
        async for sse_event in orchestrator.stream_chat(
            session_id=session_id,
            tenant_id=tenant_id,
            user_id=user_id,
            query="Hello",
            correlation_id=correlation_id,
            workspace_id=workspace_id,
        ):
            events.append(sse_event)

        assert len(events) == 1
        raw_sse = events[0]
        assert "event: error\n" in raw_sse

        for line in raw_sse.split("\n"):
            if line.startswith("data: "):
                data = json.loads(line[6:])
                assert data["code"] == "UNAUTHORIZED"
                assert data["correlation_id"] == correlation_id
                assert data["recoverable"] is False


@pytest.mark.asyncio
async def test_unexpected_internal_exception_sanitized():
    """Test that unexpected generic exceptions emit sanitized INTERNAL_ERROR without leaking internals."""
    mock_ai_wrapper = MagicMock()
    mock_repo = MagicMock()
    mock_repo.list_messages = AsyncMock(return_value=[])
    mock_repo.add_message = AsyncMock(
        side_effect=RuntimeError("Secret database connection string leaked or internal failure")
    )

    orchestrator = ChatOrchestrator(chat_repo=mock_repo, ai_wrapper_service=mock_ai_wrapper)

    session_id = str(uuid.uuid4())
    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    correlation_id = str(uuid.uuid4())
    workspace_id = uuid.uuid4()

    with patch("backend.modules.chat.services.chat_orchestrator.get_session_factory") as mock_factory, \
         patch("backend.modules.chat.services.chat_orchestrator.ChatRepository", return_value=mock_repo), \
         patch("backend.modules.chat.services.chat_orchestrator.get_redis_client") as mock_redis:

        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_factory.return_value = MagicMock(return_value=mock_session)

        events = []
        async for sse_event in orchestrator.stream_chat(
            session_id=session_id,
            tenant_id=tenant_id,
            user_id=user_id,
            query="Hello",
            correlation_id=correlation_id,
            workspace_id=workspace_id,
        ):
            events.append(sse_event)

        assert len(events) == 1
        raw_sse = events[0]

        for line in raw_sse.split("\n"):
            if line.startswith("data: "):
                data = json.loads(line[6:])
                assert data["code"] == "INTERNAL_ERROR"
                assert data["message"] == "An internal error occurred during generation."
                # Assert secret details are NOT leaked to client
                assert "Secret database connection" not in raw_sse
                assert data["recoverable"] is False
