"""Unit tests for ChatOrchestrator mid-stream interruption accounting (`WP-3C Phase 1`).

Verifies:
1. Mid-stream abort (chunks_yielded > 0) marks is_interrupted=True and persists partial assistant message to DB.
2. Mid-stream abort invokes QuotaGovernor to deduct tokens for generated text (zero free tokens on abort).
3. Mid-stream abort enforces zero provider stitching and emits terminal error event.
4. Client cancellation (CancelledError) properly persists partial message and charges quota.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from backend.document.models.document import Document
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember
from backend.modules.chat.models.chat_session import ChatSession
from backend.modules.chat.services.chat_orchestrator import ChatOrchestrator
from backend.modules.generation.schemas.generation_dto import (
    StreamingGenerationChunkDTO,
)


class MockRedisPipeline:
    def __init__(self, parent_client):
        self.parent = parent_client
        self.commands = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None

    def rpush(self, key, value):
        self.commands.append(("rpush", key, value))

    def expire(self, key, ttl):
        self.commands.append(("expire", key, ttl))

    async def execute(self, raise_on_error=True):
        return [True, True]


@pytest.fixture
def mock_redis(mocker):
    client = MagicMock()
    client.lrange = AsyncMock(return_value=[])

    def _pipeline(transaction=True):
        return MockRedisPipeline(client)

    client.pipeline = MagicMock(side_effect=_pipeline)
    mocker.patch(
        "backend.modules.chat.services.chat_orchestrator.get_redis_client",
        return_value=client,
    )
    return client


@pytest.fixture
def orchestrator_harness(mocker, mock_redis):
    session_mock = AsyncMock()
    maker = MagicMock()
    maker.return_value.__aenter__.return_value = session_mock
    maker.return_value.__aexit__.return_value = None
    mocker.patch(
        "backend.modules.chat.services.chat_orchestrator.get_session_factory",
        return_value=maker,
    )

    repo_mock = MagicMock()
    repo_mock.list_messages = AsyncMock(return_value=[])
    repo_mock.add_message = AsyncMock(return_value=None)
    mocker.patch(
        "backend.modules.chat.services.chat_orchestrator.ChatRepository",
        return_value=repo_mock,
    )

    # Mock QuotaGovernor
    quota_mock = MagicMock()
    quota_mock.record_token_usage = AsyncMock(return_value=True)
    mocker.patch(
        "backend.modules.analytics.services.quota.QuotaGovernor",
        return_value=quota_mock,
    )

    def configure_db(user_id_val: str, session_id_val: str, ws_id_val: str):
        fake_session = MagicMock(spec=ChatSession)
        fake_session.id = session_id_val
        fake_session.user_id = user_id_val
        fake_session.tenant_id = ws_id_val

        fake_member = MagicMock(spec=WorkspaceMember)
        fake_member.workspace_id = uuid.UUID(ws_id_val)
        fake_member.user_id = uuid.UUID(user_id_val)
        fake_member.status = MemberStatus.ACTIVE.value
        fake_member.is_deleted = False

        fake_doc = MagicMock(spec=Document)

        def _exec_side_effect(stmt, *args, **kwargs):
            mock_res = MagicMock()
            sql_str = str(stmt).lower()
            if "chat_sessions" in sql_str:
                mock_res.scalars.return_value.first.return_value = fake_session
            elif "workspace_members" in sql_str:
                mock_res.scalars.return_value.first.return_value = fake_member
            elif "documents" in sql_str:
                mock_res.scalars.return_value.first.return_value = fake_doc
            else:
                mock_res.scalars.return_value.first.return_value = None
                mock_res.scalar_one_or_none.return_value = None
            return mock_res

        session_mock.execute = AsyncMock(side_effect=_exec_side_effect)

    return {
        "session": session_mock,
        "repo": repo_mock,
        "quota": quota_mock,
        "configure_db": configure_db,
    }


@pytest.mark.asyncio
async def test_mid_stream_abort_persists_partial_message_and_deducts_quota(
    orchestrator_harness, mocker
):
    """When stream aborts mid-generation, orchestrator marks is_interrupted=True,

    persists partial text to DB, and invokes QuotaGovernor to deduct tokens.
    """
    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    ws_id = str(uuid.uuid4())
    corr_id = str(uuid.uuid4())
    orchestrator_harness["configure_db"](user_id, session_id, ws_id)

    # Mock AI wrapper generator to emit 2 chunks and then raise an exception
    async def mock_stream_chunks(*args, **kwargs):
        yield StreamingGenerationChunkDTO(
            chunk_index=0,
            text_delta="Partial generated ",
            is_final=False,
            is_fully_grounded=False,
            citations_delta=[],
            correlation_id=corr_id,
        )
        yield StreamingGenerationChunkDTO(
            chunk_index=1,
            text_delta="text before abort.",
            is_final=False,
            is_fully_grounded=False,
            citations_delta=[],
            correlation_id=corr_id,
        )
        # Abrupt mid-stream provider abort!
        raise RuntimeError("LLM provider connection reset mid-stream")

    wrapper_mock = MagicMock()
    wrapper_mock.stream_request = MagicMock(side_effect=mock_stream_chunks)

    orchestrator = ChatOrchestrator(
        chat_repo=orchestrator_harness["repo"],
        ai_wrapper_service=wrapper_mock,
    )

    events = []
    async for event in orchestrator.stream_chat(
        session_id=session_id,
        user_id=user_id,
        tenant_id=ws_id,
        query="What is Veritas-RAG?",
        correlation_id=corr_id,
        workspace_id=uuid.UUID(ws_id),
    ):
        events.append(event)

    # 1. Verify chunks were yielded and error event was emitted
    assert len(events) >= 3  # progress, chunk 0, chunk 1, error
    assert any("event: error" in e for e in events)

    # 2. Verify partial assistant message was persisted with is_interrupted=True
    repo = orchestrator_harness["repo"]
    assert repo.add_message.called
    call_args = repo.add_message.call_args[1]
    dto = call_args["dto"]
    assert dto.role == "assistant"
    assert "Partial generated text before abort." in dto.message
    assert dto.metadata_json.get("is_interrupted") is True
    assert dto.metadata_json.get("status") == "PARTIAL"

    # 3. Verify QuotaGovernor.record_token_usage was called to charge for consumed tokens
    quota = orchestrator_harness["quota"]
    assert quota.record_token_usage.called
    quota_call = quota.record_token_usage.call_args[1]
    assert quota_call["workspace_id"] == uuid.UUID(ws_id)
    assert quota_call["completion_tokens"] > 0
    assert quota_call["prompt_tokens"] > 0


@pytest.mark.asyncio
async def test_client_cancellation_charges_quota_and_saves_interrupted(
    orchestrator_harness, mocker
):
    """When client disconnects (asyncio.CancelledError), partial tokens are charged to quota."""
    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    ws_id = str(uuid.uuid4())
    corr_id = str(uuid.uuid4())
    orchestrator_harness["configure_db"](user_id, session_id, ws_id)

    async def mock_stream_cancelled(*args, **kwargs):
        yield StreamingGenerationChunkDTO(
            chunk_index=0,
            text_delta="Tokens before client disconnect.",
            is_final=False,
            is_fully_grounded=False,
            citations_delta=[],
            correlation_id=corr_id,
        )
        raise asyncio.CancelledError()

    wrapper_mock = MagicMock()
    wrapper_mock.stream_request = MagicMock(side_effect=mock_stream_cancelled)

    orchestrator = ChatOrchestrator(
        chat_repo=orchestrator_harness["repo"],
        ai_wrapper_service=wrapper_mock,
    )

    with pytest.raises(asyncio.CancelledError):
        async for _ in orchestrator.stream_chat(
            session_id=session_id,
            user_id=user_id,
            tenant_id=ws_id,
            query="Tell me a story",
            correlation_id=corr_id,
            workspace_id=uuid.UUID(ws_id),
        ):
            pass

    # Verify partial assistant message was persisted with is_interrupted=True
    repo = orchestrator_harness["repo"]
    assert repo.add_message.called
    dto = repo.add_message.call_args[1]["dto"]
    assert dto.metadata_json.get("is_interrupted") is True

    # Verify QuotaGovernor was called
    quota = orchestrator_harness["quota"]
    assert quota.record_token_usage.called
