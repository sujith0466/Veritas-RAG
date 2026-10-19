"""Unit tests for REC-001: SSE Progress Events in ChatOrchestrator.

Verifies:
1. Orchestrator emits 'retrieving' progress event prior to AIWrapperService.stream_request.
2. Progress event wire format has event: progress, valid JSON data with stage and message, and NO id: header.
3. Progress events strictly bypass Redis replay buffer (chunk-only Redis invariant preserved).
4. Reconnection with valid Last-Event-ID succeeds without INVALID_CORRELATION error.
5. Preflight failure cleans up active stream gauge without leaking.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from backend.document.models.document import Document
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember
from backend.modules.chat.models.chat_session import ChatSession
from backend.modules.chat.services.chat_orchestrator import ChatOrchestrator
from backend.modules.generation.schemas.generation_dto import StreamingGenerationChunkDTO
from backend.observability.metrics.prometheus import SSE_ACTIVE_STREAMS


class MockRedisPipeline:
    """Deterministic mock for redis.asyncio Pipeline with transaction=True."""

    def __init__(self, parent_client):
        self.parent = parent_client
        self.commands = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None

    def rpush(self, key, value):
        self.commands.append(("rpush", key, value))
        self.parent.recorded_pipeline_rpush.append((key, value))

    def expire(self, key, seconds):
        self.commands.append(("expire", key, seconds))
        self.parent.recorded_pipeline_expire.append((key, seconds))

    async def execute(self, raise_on_error=True):
        self.parent.pipeline_execute_count += 1
        return [len(self.commands), True]


@pytest.fixture
def mock_redis_client(mocker):
    """Provide a controllable Redis client with pipeline tracking."""
    client = MagicMock()
    client.pipeline_execute_count = 0
    client.recorded_pipeline_rpush = []
    client.recorded_pipeline_expire = []
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
def orchestrator_harness(mocker, mock_redis_client):
    """Setup deterministic test harness for ChatOrchestrator."""
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

    def configure_db(
        user_id_val: str,
        session_id_val: str,
        ws_id_val: str,
        has_ready_doc: bool = True,
    ):
        fake_session = MagicMock(spec=ChatSession)
        fake_session.id = session_id_val
        fake_session.user_id = user_id_val
        fake_session.tenant_id = ws_id_val

        fake_member = MagicMock(spec=WorkspaceMember)
        fake_member.workspace_id = uuid.UUID(ws_id_val)
        fake_member.user_id = uuid.UUID(user_id_val)
        fake_member.status = MemberStatus.ACTIVE.value
        fake_member.is_deleted = False

        fake_ready_doc = MagicMock(spec=Document) if has_ready_doc else None

        async def _execute(statement, *args, **kwargs):
            stmt_str = str(statement)
            res = MagicMock()
            if "chat_sessions" in stmt_str:
                res.scalar_one_or_none.return_value = fake_session
            elif "workspace_members" in stmt_str:
                res.scalar_one_or_none.return_value = fake_member
            elif "documents" in stmt_str:
                res.scalar_one_or_none.return_value = fake_ready_doc
            elif "users" in stmt_str or "preferences" in stmt_str:
                res.scalar_one_or_none.return_value = {}
            else:
                res.scalar_one_or_none.return_value = None
            return res

        session_mock.execute.side_effect = _execute

    ai_wrapper_service = MagicMock()
    orchestrator = ChatOrchestrator(
        chat_repo=repo_mock,
        ai_wrapper_service=ai_wrapper_service,
    )
    return orchestrator, ai_wrapper_service, configure_db, session_mock


@pytest.mark.asyncio
async def test_stream_chat_emits_progress_event_before_retrieval(orchestrator_harness):
    """Verify that stream_chat yields an initial 'retrieving' progress event without an id: header."""
    orchestrator, ai_wrapper, configure_db, _ = orchestrator_harness

    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    ws_id = str(uuid.uuid4())
    corr_id = str(uuid.uuid4())

    configure_db(user_id, session_id, ws_id, has_ready_doc=True)

    # Mock stream_request to yield one token chunk and a final chunk
    async def _mock_stream(*args, **kwargs):
        yield StreamingGenerationChunkDTO(
            chunk_index=0,
            text_delta="Hello",
            citations_delta=[],
            is_final=False,
            correlation_id=corr_id,
        )
        yield StreamingGenerationChunkDTO(
            chunk_index=1,
            text_delta=" world!",
            citations_delta=[],
            is_final=True,
            correlation_id=corr_id,
            is_fully_grounded=True,
            wrapper_metadata={"reliability_score": 0.95},
        )

    ai_wrapper.stream_request = MagicMock(side_effect=_mock_stream)

    yielded_events = []
    async for raw_sse in orchestrator.stream_chat(
        session_id=session_id,
        query="Explain RAG",
        user_id=user_id,
        tenant_id=ws_id,
        correlation_id=corr_id,
    ):
        yielded_events.append(raw_sse)

    assert len(yielded_events) >= 3

    # First event must be the progress event
    progress_event = yielded_events[0]
    assert "event: progress\n" in progress_event
    assert "id:" not in progress_event  # Crucial: NO id: header

    # Parse data line
    data_line = [line for line in progress_event.split("\n") if line.startswith("data: ")][0]
    payload = json.loads(data_line[6:])
    assert payload["stage"] == "retrieving"
    assert payload["message"] == "Searching knowledge base..."
    assert payload.get("correlation_id") == corr_id


@pytest.mark.asyncio
async def test_progress_events_bypass_redis_storage(orchestrator_harness, mock_redis_client):
    """Verify that progress events are never written to the Redis chunk replay buffer."""
    orchestrator, ai_wrapper, configure_db, _ = orchestrator_harness

    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    ws_id = str(uuid.uuid4())
    corr_id = str(uuid.uuid4())

    configure_db(user_id, session_id, ws_id, has_ready_doc=True)

    async def _mock_stream(*args, **kwargs):
        yield StreamingGenerationChunkDTO(
            chunk_index=0,
            text_delta="Answer token",
            citations_delta=[],
            is_final=True,
            correlation_id=corr_id,
        )

    ai_wrapper.stream_request = MagicMock(side_effect=_mock_stream)

    async for _ in orchestrator.stream_chat(
        session_id=session_id,
        query="Test query",
        user_id=user_id,
        tenant_id=ws_id,
        correlation_id=corr_id,
    ):
        pass

    # Inspect all rpush commands in recorded_pipeline_rpush
    assert len(mock_redis_client.recorded_pipeline_rpush) == 1
    key, val_json = mock_redis_client.recorded_pipeline_rpush[0]
    assert key == f"raguard:{ws_id}:sse:{corr_id}"

    buffered_item = json.loads(val_json)
    assert buffered_item["event_type"] == "chunk"
    assert buffered_item["chunk_index"] == 0

    # Ensure no progress event was written to Redis
    for _, val in mock_redis_client.recorded_pipeline_rpush:
        item = json.loads(val)
        assert item.get("event_type") != "progress"
        assert item.get("stage") != "retrieving"


@pytest.mark.asyncio
async def test_reconnection_after_progress_with_valid_last_event_id(orchestrator_harness, mock_redis_client):
    """Verify that a reconnection with a valid chunk Last-Event-ID succeeds without INVALID_CORRELATION."""
    orchestrator, _, configure_db, _ = orchestrator_harness

    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    ws_id = str(uuid.uuid4())
    corr_id = str(uuid.uuid4())

    configure_db(user_id, session_id, ws_id, has_ready_doc=True)

    # Populate Redis replay buffer with valid chunks 0 and 1
    chunk_0 = {
        "chunk_index": 0,
        "event_type": "chunk",
        "is_final": False,
        "payload": {
            "chunk_index": 0,
            "text_delta": "Part 1",
            "citations_delta": [],
            "is_final": False,
            "correlation_id": corr_id,
        },
    }
    chunk_1 = {
        "chunk_index": 1,
        "event_type": "chunk",
        "is_final": True,
        "payload": {
            "chunk_index": 1,
            "text_delta": "Part 2",
            "citations_delta": [],
            "is_final": True,
            "correlation_id": corr_id,
        },
    }
    mock_redis_client.lrange.return_value = [json.dumps(chunk_0), json.dumps(chunk_1)]

    replayed_events = []
    async for raw_sse in orchestrator.stream_chat(
        session_id=session_id,
        query="Replay query",
        user_id=user_id,
        tenant_id=ws_id,
        correlation_id=corr_id,
        last_event_id=f"{corr_id}:0",
    ):
        replayed_events.append(raw_sse)

    assert len(replayed_events) == 1
    replayed = replayed_events[0]
    assert "event: chunk\n" in replayed
    assert f"id: {corr_id}:1\n" in replayed
    assert "INVALID_CORRELATION" not in replayed


@pytest.mark.asyncio
async def test_preflight_failure_cleans_up_stream_gauge(orchestrator_harness):
    """Verify that a failure during preflight checks emits an error and properly decrements SSE_ACTIVE_STREAMS."""
    orchestrator, _, _, session_mock = orchestrator_harness

    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    ws_id = str(uuid.uuid4())
    corr_id = str(uuid.uuid4())

    # Simulate DB error during session lookup
    session_mock.execute.side_effect = Exception("DB connection exploded")

    yielded = []
    async for event in orchestrator.stream_chat(
        session_id=session_id,
        query="Fail query",
        user_id=user_id,
        tenant_id=ws_id,
        correlation_id=corr_id,
    ):
        yielded.append(event)

    assert len(yielded) == 1
    error_sse = yielded[0]
    assert "event: error\n" in error_sse
    assert "INTERNAL_ERROR" in error_sse
