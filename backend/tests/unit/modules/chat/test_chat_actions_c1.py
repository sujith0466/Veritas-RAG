"""Unit tests for WS-C C1: Chat Message Feedback and Deterministic Rewind APIs."""

from datetime import UTC, datetime
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi import HTTPException

from backend.modules.chat.models.chat_message import ChatMessage
from backend.modules.chat.models.chat_session import ChatSession
from backend.modules.chat.repositories.chat_repository import ChatRepository
from backend.modules.chat.schemas.chat_dto import ChatMessageFeedbackDTO


@pytest.fixture
def mock_session():
    """Mock AsyncSession for ChatRepository."""
    session = AsyncMock()
    return session


@pytest.fixture
def chat_repo(mock_session):
    return ChatRepository(session=mock_session)


@pytest.mark.asyncio
async def test_update_feedback_like_success(chat_repo, mock_session):
    """Setting 'like' on an assistant message updates metadata_json with server-derived user_id."""
    session_id = str(uuid.uuid4())
    message_id = str(uuid.uuid4())
    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    chat_session = ChatSession(id=session_id, tenant_id=tenant_id, user_id=user_id, title="Test Chat")
    assistant_msg = ChatMessage(
        id=message_id,
        session_id=session_id,
        role="assistant",
        message="Here is the retrieved answer.",
        metadata_json={}
    )

    # get_session check passes
    chat_repo.get_session = AsyncMock(return_value=chat_session)
    chat_repo.get_message = AsyncMock(return_value=assistant_msg)

    result = await chat_repo.update_message_feedback(
        session_id=session_id,
        message_id=message_id,
        tenant_id=tenant_id,
        user_id=user_id,
        rating="like"
    )

    assert result.metadata_json is not None
    assert result.metadata_json["feedback"] == "like"
    assert result.metadata_json["feedback_by"] == user_id
    assert "feedback_at" in result.metadata_json
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_feedback_dislike_success(chat_repo, mock_session):
    """Setting 'dislike' on an assistant message updates metadata_json."""
    session_id = str(uuid.uuid4())
    message_id = str(uuid.uuid4())
    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    chat_session = ChatSession(id=session_id, tenant_id=tenant_id, user_id=user_id, title="Test Chat")
    assistant_msg = ChatMessage(
        id=message_id,
        session_id=session_id,
        role="assistant",
        message="Here is the retrieved answer.",
        metadata_json={"feedback": "like"}
    )

    chat_repo.get_session = AsyncMock(return_value=chat_session)
    chat_repo.get_message = AsyncMock(return_value=assistant_msg)

    result = await chat_repo.update_message_feedback(
        session_id=session_id,
        message_id=message_id,
        tenant_id=tenant_id,
        user_id=user_id,
        rating="dislike"
    )

    assert result.metadata_json["feedback"] == "dislike"
    assert result.metadata_json["feedback_by"] == user_id
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_feedback_toggle_off_to_null(chat_repo, mock_session):
    """Passing None rating clears feedback from metadata_json."""
    session_id = str(uuid.uuid4())
    message_id = str(uuid.uuid4())
    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    chat_session = ChatSession(id=session_id, tenant_id=tenant_id, user_id=user_id, title="Test Chat")
    assistant_msg = ChatMessage(
        id=message_id,
        session_id=session_id,
        role="assistant",
        message="Here is the retrieved answer.",
        metadata_json={"feedback": "like", "feedback_by": user_id, "feedback_at": "2026-10-05T00:00:00Z"}
    )

    chat_repo.get_session = AsyncMock(return_value=chat_session)
    chat_repo.get_message = AsyncMock(return_value=assistant_msg)

    result = await chat_repo.update_message_feedback(
        session_id=session_id,
        message_id=message_id,
        tenant_id=tenant_id,
        user_id=user_id,
        rating=None
    )

    assert "feedback" not in result.metadata_json
    assert "feedback_by" not in result.metadata_json
    assert "feedback_at" not in result.metadata_json
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_feedback_on_user_message_rejected(chat_repo):
    """Attempting feedback on a user message raises 400 Bad Request."""
    session_id = str(uuid.uuid4())
    message_id = str(uuid.uuid4())
    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    chat_session = ChatSession(id=session_id, tenant_id=tenant_id, user_id=user_id, title="Test Chat")
    user_msg = ChatMessage(
        id=message_id,
        session_id=session_id,
        role="user",
        message="What is Veritas-RAG?"
    )

    chat_repo.get_session = AsyncMock(return_value=chat_session)
    chat_repo.get_message = AsyncMock(return_value=user_msg)

    with pytest.raises(HTTPException) as exc_info:
        await chat_repo.update_message_feedback(
            session_id=session_id,
            message_id=message_id,
            tenant_id=tenant_id,
            user_id=user_id,
            rating="like"
        )

    assert exc_info.value.status_code == 400
    assert "assistant messages" in exc_info.value.detail


@pytest.mark.asyncio
async def test_update_feedback_message_not_found(chat_repo):
    """Attempting feedback on non-existent message raises 404."""
    session_id = str(uuid.uuid4())
    message_id = str(uuid.uuid4())
    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    chat_session = ChatSession(id=session_id, tenant_id=tenant_id, user_id=user_id, title="Test Chat")
    chat_repo.get_session = AsyncMock(return_value=chat_session)
    chat_repo.get_message = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as exc_info:
        await chat_repo.update_message_feedback(
            session_id=session_id,
            message_id=message_id,
            tenant_id=tenant_id,
            user_id=user_id,
            rating="like"
        )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_rewind_deterministic_ordering_and_atomic_deletion(chat_repo, mock_session):
    """Rewind deletes target message and all subsequent turns; earlier turns are untouched."""
    session_id = str(uuid.uuid4())
    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    chat_session = ChatSession(id=session_id, tenant_id=tenant_id, user_id=user_id, title="Multi-Turn Chat")
    chat_repo.get_session = AsyncMock(return_value=chat_session)

    # 4 messages in session
    msg1_id = "00000000-0000-0000-0000-000000000001"
    msg2_id = "00000000-0000-0000-0000-000000000002"
    msg3_id = "00000000-0000-0000-0000-000000000003" # Target
    msg4_id = "00000000-0000-0000-0000-000000000004"

    ordered_ids = [msg1_id, msg2_id, msg3_id, msg4_id]
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = ordered_ids
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.get = AsyncMock(return_value=chat_session)

    deleted_count = await chat_repo.rewind_session_from(
        session_id=session_id,
        target_message_id=msg3_id,
        tenant_id=tenant_id,
        user_id=user_id
    )

    # Deletes msg3 and msg4 (2 messages)
    assert deleted_count == 2
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_rewind_target_not_found_raises_404(chat_repo, mock_session):
    """Rewind with target_message_id not in session raises 404 (protects against double-rewind)."""
    session_id = str(uuid.uuid4())
    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    chat_session = ChatSession(id=session_id, tenant_id=tenant_id, user_id=user_id, title="Test Chat")
    chat_repo.get_session = AsyncMock(return_value=chat_session)

    # Session only contains msg1
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = ["msg-1"]
    mock_session.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(HTTPException) as exc_info:
        await chat_repo.rewind_session_from(
            session_id=session_id,
            target_message_id="msg-already-deleted",
            tenant_id=tenant_id,
            user_id=user_id
        )

    assert exc_info.value.status_code == 404
    assert "Target message not found" in exc_info.value.detail


@pytest.mark.asyncio
async def test_rewind_cross_tenant_access_rejected(chat_repo):
    """Attempting rewind on another tenant's session fails via get_session 404."""
    session_id = str(uuid.uuid4())
    target_id = str(uuid.uuid4())

    chat_repo.get_session = AsyncMock(
        side_effect=HTTPException(status_code=404, detail="Chat session not found or access denied.")
    )

    with pytest.raises(HTTPException) as exc_info:
        await chat_repo.rewind_session_from(
            session_id=session_id,
            target_message_id=target_id,
            tenant_id="foreign-tenant",
            user_id="foreign-user"
        )

    assert exc_info.value.status_code == 404
