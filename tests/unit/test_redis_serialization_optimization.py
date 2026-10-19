"""Unit tests for REC-003: Redis & JSON Serialization Optimization in ChatOrchestrator.

Verifies:
1. Pipelined Redis operations (rpush and expire executed atomically via async pipeline).
2. Write failure isolation (live SSE delivery continues, further buffering disabled on RedisError).
3. Propagation of unexpected non-Redis exceptions during pipeline write and replay read.
4. Exact character-level JSON serialization compatibility with Pydantic baseline.
5. Strict record-by-record replay buffer validation (schema, types, contiguity, terminal completion).
6. Complete rejection of malformed buffers without leaking partially replayed chunks.
7. Error handling and telemetry isolation on Redis read failures and cache misses.
8. Complete elimination of speculative secondary generation on incomplete reconnects.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError, RedisError, TimeoutError as RedisTimeoutError

from backend.document.models.document import Document
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember
from backend.modules.chat.models.chat_session import ChatSession
from backend.modules.chat.services.chat_orchestrator import ChatOrchestrator
from backend.modules.generation.schemas.generation_dto import (
    CitationDTO,
    StreamingGenerationChunkDTO,
)
from backend.observability.metrics.prometheus import (
    SSE_ACTIVE_STREAMS,
    SSE_REDIS_BUFFER_HITS_TOTAL,
    SSE_REDIS_BUFFER_MISSES_TOTAL,
    SSE_REPLAYED_CHUNKS_TOTAL,
)


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
        if self.parent.pipeline_error:
            raise self.parent.pipeline_error
        return [len(self.commands), True]


@pytest.fixture
def mock_redis_client(mocker):
    """Provide a controllable Redis client with pipeline tracking."""
    client = MagicMock()
    client.pipeline_error = None
    client.pipeline_execute_count = 0
    client.recorded_pipeline_rpush = []
    client.recorded_pipeline_expire = []
    client.lrange = AsyncMock(return_value=[])

    def _pipeline(transaction=True):
        client.pipeline_called_with_transaction = transaction
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


# ==============================================================================
# 1. Serialization Output Equality Tests
# ==============================================================================

def test_json_serialization_exact_character_match():
    """Verify that compact json.dumps(chunk.model_dump(mode='json'), ensure_ascii=False) produces identical SSE data."""
    corr_id = str(uuid.uuid4())

    chunks = [
        # 1. Text chunk with special characters, Unicode, emoji, quotes, newlines, tabs
        StreamingGenerationChunkDTO(
            chunk_index=0,
            text_delta="Hello, world! Special chars: <>&'\"\n\t \\ \u2764\ufe0f",
            citations_delta=[],
            is_final=False,
            correlation_id=corr_id,
        ),
        # 2. Intermediate chunk with punctuation
        StreamingGenerationChunkDTO(
            chunk_index=1,
            text_delta=" intermediate payload with punctuation: , : { } [ ]",
            citations_delta=[],
            is_final=False,
            correlation_id=corr_id,
        ),
        # 3. Terminal chunk with citations and metadata
        StreamingGenerationChunkDTO(
            chunk_index=2,
            text_delta="",
            citations_delta=[
                CitationDTO(
                    citation_index=1,
                    chunk_id="chk-789",
                    document_id="doc-123",
                    title="Document A.pdf",
                    excerpt="Referenced evidence text with \n and \t.",
                    relevance_score=0.92,
                )
            ],
            is_final=True,
            is_fully_grounded=True,
            wrapper_metadata={"reliability_score": 0.98},
            correlation_id=corr_id,
        ),
    ]

    for chunk in chunks:
        baseline_json = chunk.model_dump_json()
        optimized_dict = chunk.model_dump(mode="json")
        optimized_json = json.dumps(optimized_dict, separators=(",", ":"), ensure_ascii=False)

        assert optimized_json == baseline_json, (
            f"Serialization mismatch for chunk {chunk.chunk_index}:\n"
            f"Expected: {baseline_json}\n"
            f"Actual:   {optimized_json}"
        )


# ==============================================================================
# 2. Redis Pipelining Verification Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_redis_pipelined_rpush_and_expire(
    orchestrator_harness, mock_redis_client
):
    """Verify RPUSH and EXPIRE are bundled together in an atomic pipeline call per chunk."""
    orchestrator, ai_wrapper, configure_db, _ = orchestrator_harness
    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    ws_id = str(uuid.uuid4())
    corr_id = str(uuid.uuid4())

    configure_db(user_id, session_id, ws_id, has_ready_doc=True)

    async def mock_stream(*args, **kwargs):
        yield StreamingGenerationChunkDTO(
            chunk_index=0,
            text_delta="Token 1",
            citations_delta=[],
            is_final=False,
            correlation_id=corr_id,
        )
        yield StreamingGenerationChunkDTO(
            chunk_index=1,
            text_delta="Token 2",
            citations_delta=[],
            is_final=True,
            is_fully_grounded=True,
            correlation_id=corr_id,
        )

    ai_wrapper.stream_request.return_value = mock_stream()

    events = []
    async for event in orchestrator.stream_chat(
        session_id=session_id,
        tenant_id=ws_id,
        user_id=user_id,
        query="Test query",
        correlation_id=corr_id,
    ):
        events.append(event)

    # Initial progress event + 2 chunks yielded + done event (REC-001 contract)
    assert len(events) == 4
    assert "event: progress" in events[0]
    chunk_events = [e for e in events if "event: chunk" in e]
    assert len(chunk_events) == 2
    assert any("event: done" in e for e in events)

    # Pipeline was called twice (once per chunk) with transaction=True
    assert mock_redis_client.pipeline.call_count == 2
    assert mock_redis_client.pipeline_called_with_transaction is True
    assert mock_redis_client.pipeline_execute_count == 2

    # Verify command pairing and parameters
    expected_key = f"raguard:{ws_id}:sse:{corr_id}"
    assert len(mock_redis_client.recorded_pipeline_rpush) == 2
    assert len(mock_redis_client.recorded_pipeline_expire) == 2

    for key, payload_str in mock_redis_client.recorded_pipeline_rpush:
        assert key == expected_key
        payload = json.loads(payload_str)
        assert "chunk_index" in payload
        assert "payload" in payload
        assert "is_final" in payload
        assert payload["event_type"] == "chunk"

    for key, ttl in mock_redis_client.recorded_pipeline_expire:
        assert key == expected_key
        assert ttl == 300


# ==============================================================================
# 3. Redis Write Failure & Exception Scoping Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_redis_write_failure_shields_live_stream(
    orchestrator_harness, mock_redis_client
):
    """When Redis pipeline raises RedisError, live stream delivery continues and buffering is disabled."""
    orchestrator, ai_wrapper, configure_db, _ = orchestrator_harness
    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    ws_id = str(uuid.uuid4())
    corr_id = str(uuid.uuid4())

    configure_db(user_id, session_id, ws_id, has_ready_doc=True)

    # Simulate Redis connection drop during pipeline.execute() using RedisConnectionError
    mock_redis_client.pipeline_error = RedisConnectionError("Redis cluster unreachable")

    async def mock_stream(*args, **kwargs):
        yield StreamingGenerationChunkDTO(
            chunk_index=0,
            text_delta="Token 1",
            citations_delta=[],
            is_final=False,
            correlation_id=corr_id,
        )
        yield StreamingGenerationChunkDTO(
            chunk_index=1,
            text_delta="Token 2",
            citations_delta=[],
            is_final=True,
            is_fully_grounded=True,
            correlation_id=corr_id,
        )

    ai_wrapper.stream_request.return_value = mock_stream()

    events = []
    async for event in orchestrator.stream_chat(
        session_id=session_id,
        tenant_id=ws_id,
        user_id=user_id,
        query="Test query",
        correlation_id=corr_id,
    ):
        events.append(event)

    # Initial progress event + both chunks + done event are successfully delivered to client!
    assert len(events) == 4
    assert "event: progress" in events[0]
    assert any("Token 1" in e for e in events)
    assert any("Token 2" in e for e in events)
    assert any("event: done" in e for e in events)

    # Only 1 pipeline execution was attempted because subsequent chunks skipped buffering
    assert mock_redis_client.pipeline_execute_count == 1
    assert mock_redis_client.pipeline.call_count == 1


@pytest.mark.asyncio
async def test_unexpected_non_redis_write_exception_propagates(
    orchestrator_harness, mock_redis_client
):
    """Unexpected programming exception during pipeline execution must NOT be caught as RedisError."""
    orchestrator, ai_wrapper, configure_db, _ = orchestrator_harness
    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    ws_id = str(uuid.uuid4())
    corr_id = str(uuid.uuid4())

    configure_db(user_id, session_id, ws_id, has_ready_doc=True)

    # Inject a non-Redis exception (e.g. TypeError or RuntimeError)
    mock_redis_client.pipeline_error = TypeError("Simulated programming bug in pipeline")

    async def mock_stream(*args, **kwargs):
        yield StreamingGenerationChunkDTO(
            chunk_index=0,
            text_delta="Token 1",
            citations_delta=[],
            is_final=False,
            correlation_id=corr_id,
        )

    ai_wrapper.stream_request.return_value = mock_stream()

    events = []
    async for event in orchestrator.stream_chat(
        session_id=session_id,
        tenant_id=ws_id,
        user_id=user_id,
        query="Test query",
        correlation_id=corr_id,
    ):
        events.append(event)

    # Must NOT be caught by Redis fallback (which would have shielded live SSE and delivered Token 1);
    # instead, the unexpected exception aborts generation after initial progress event and yields INTERNAL_ERROR.
    assert len(events) == 2
    assert "event: progress" in events[0]
    assert "INTERNAL_ERROR" in events[1]
    assert not any("Token 1" in e for e in events)


# ==============================================================================
# 4. Canonical Replay Integrity & Schema Validation Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_replay_completed_buffer_success(
    orchestrator_harness, mock_redis_client, mocker
):
    """Valid completed contiguous buffer replays chunks after last_chunk_index."""
    orchestrator, ai_wrapper, _, _ = orchestrator_harness
    ws_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    corr_id = str(uuid.uuid4())

    mock_hits = mocker.patch.object(SSE_REDIS_BUFFER_HITS_TOTAL, "inc")
    mock_replayed = mocker.patch.object(SSE_REPLAYED_CHUNKS_TOTAL, "inc")
    mock_misses = mocker.patch.object(SSE_REDIS_BUFFER_MISSES_TOTAL, "inc")
    mock_active = mocker.patch.object(SSE_ACTIVE_STREAMS, "dec")

    # Prepare complete 3-chunk buffer in Redis matching StreamingGenerationChunkDTO schema
    raw_buffer = [
        json.dumps({
            "chunk_index": 0,
            "event_type": "chunk",
            "payload": {
                "chunk_index": 0,
                "text_delta": "Part 0",
                "citations_delta": [],
                "is_final": False,
                "correlation_id": corr_id,
            },
            "is_final": False,
        }, separators=(",", ":")).encode("utf-8"),
        json.dumps({
            "chunk_index": 1,
            "event_type": "chunk",
            "payload": {
                "chunk_index": 1,
                "text_delta": "Part 1",
                "citations_delta": [],
                "is_final": False,
                "correlation_id": corr_id,
            },
            "is_final": False,
        }, separators=(",", ":")).encode("utf-8"),
        json.dumps({
            "chunk_index": 2,
            "event_type": "chunk",
            "payload": {
                "chunk_index": 2,
                "text_delta": "Part 2",
                "citations_delta": [],
                "is_final": True,
                "correlation_id": corr_id,
            },
            "is_final": True,
        }, separators=(",", ":")).encode("utf-8"),
    ]
    mock_redis_client.lrange.return_value = raw_buffer

    # Client reconnects having already seen chunk 0
    last_event_id = f"{corr_id}:0"

    events = []
    async for event in orchestrator.stream_chat(
        session_id=session_id,
        tenant_id=ws_id,
        user_id=user_id,
        query="Replay test",
        correlation_id=corr_id,
        last_event_id=last_event_id,
    ):
        events.append(event)

    # Chunks 1 and 2 should be replayed
    assert len(events) == 2
    assert "Part 1" in events[0]
    assert "Part 2" in events[1]

    # Metrics verification
    mock_hits.assert_called_once()
    assert mock_replayed.call_count == 2
    mock_misses.assert_not_called()
    mock_active.assert_called_once()

    # Zero LLM generation occurred
    ai_wrapper.stream_request.assert_not_called()


@pytest.mark.asyncio
async def test_replay_incomplete_buffer_rejected(
    orchestrator_harness, mock_redis_client, mocker
):
    """Incomplete buffer (is_final=False on last chunk) is rejected with STREAM_EXPIRED and no secondary generation."""
    orchestrator, ai_wrapper, _, _ = orchestrator_harness
    ws_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    corr_id = str(uuid.uuid4())

    mock_hits = mocker.patch.object(SSE_REDIS_BUFFER_HITS_TOTAL, "inc")
    mock_misses = mocker.patch.object(SSE_REDIS_BUFFER_MISSES_TOTAL, "inc")
    mock_active = mocker.patch.object(SSE_ACTIVE_STREAMS, "dec")

    # Buffer missing final chunk
    raw_buffer = [
        json.dumps({
            "chunk_index": 0,
            "event_type": "chunk",
            "payload": {
                "chunk_index": 0,
                "text_delta": "Part 0",
                "citations_delta": [],
                "is_final": False,
                "correlation_id": corr_id,
            },
            "is_final": False,
        }).encode("utf-8"),
        json.dumps({
            "chunk_index": 1,
            "event_type": "chunk",
            "payload": {
                "chunk_index": 1,
                "text_delta": "Part 1",
                "citations_delta": [],
                "is_final": False,
                "correlation_id": corr_id,
            },
            "is_final": False,
        }).encode("utf-8"),
    ]
    mock_redis_client.lrange.return_value = raw_buffer

    last_event_id = f"{corr_id}:0"

    events = []
    async for event in orchestrator.stream_chat(
        session_id=session_id,
        tenant_id=ws_id,
        user_id=user_id,
        query="Replay test",
        correlation_id=corr_id,
        last_event_id=last_event_id,
    ):
        events.append(event)

    assert len(events) == 1
    assert "STREAM_EXPIRED" in events[0]
    assert '"recoverable":false' in events[0] or '"recoverable": false' in events[0]

    mock_misses.assert_called_once()
    mock_hits.assert_not_called()
    mock_active.assert_called_once()
    ai_wrapper.stream_request.assert_not_called()


@pytest.mark.asyncio
async def test_replay_gapped_buffer_rejected(
    orchestrator_harness, mock_redis_client, mocker
):
    """Buffer with missing index (e.g. [0, 2]) is rejected as corrupted/invalid."""
    orchestrator, ai_wrapper, _, _ = orchestrator_harness
    ws_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    corr_id = str(uuid.uuid4())

    mock_misses = mocker.patch.object(SSE_REDIS_BUFFER_MISSES_TOTAL, "inc")

    raw_buffer = [
        json.dumps({
            "chunk_index": 0,
            "event_type": "chunk",
            "payload": {
                "chunk_index": 0,
                "text_delta": "Part 0",
                "citations_delta": [],
                "is_final": False,
                "correlation_id": corr_id,
            },
            "is_final": False,
        }).encode("utf-8"),
        json.dumps({
            "chunk_index": 2,  # Missing index 1!
            "event_type": "chunk",
            "payload": {
                "chunk_index": 2,
                "text_delta": "Part 2",
                "citations_delta": [],
                "is_final": True,
                "correlation_id": corr_id,
            },
            "is_final": True,
        }).encode("utf-8"),
    ]
    mock_redis_client.lrange.return_value = raw_buffer

    events = []
    async for event in orchestrator.stream_chat(
        session_id=session_id,
        tenant_id=ws_id,
        user_id=user_id,
        query="Replay test",
        correlation_id=corr_id,
        last_event_id=f"{corr_id}:0",
    ):
        events.append(event)

    assert len(events) == 1
    assert "STREAM_EXPIRED" in events[0]
    mock_misses.assert_called_once()
    ai_wrapper.stream_request.assert_not_called()


@pytest.mark.asyncio
async def test_replay_malformed_json_rejected(
    orchestrator_harness, mock_redis_client, mocker
):
    """Buffer containing corrupted/unparseable JSON is rejected."""
    orchestrator, ai_wrapper, _, _ = orchestrator_harness
    ws_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    corr_id = str(uuid.uuid4())

    mock_misses = mocker.patch.object(SSE_REDIS_BUFFER_MISSES_TOTAL, "inc")

    mock_redis_client.lrange.return_value = [b"NOT_VALID_JSON{"]

    events = []
    async for event in orchestrator.stream_chat(
        session_id=session_id,
        tenant_id=ws_id,
        user_id=user_id,
        query="Replay test",
        correlation_id=corr_id,
        last_event_id=f"{corr_id}:0",
    ):
        events.append(event)

    assert len(events) == 1
    assert "STREAM_EXPIRED" in events[0]
    mock_misses.assert_called_once()
    ai_wrapper.stream_request.assert_not_called()


@pytest.mark.asyncio
async def test_replay_missing_payload_rejected(
    orchestrator_harness, mock_redis_client, mocker
):
    """Entry missing 'payload' dictionary is rejected."""
    orchestrator, ai_wrapper, _, _ = orchestrator_harness
    ws_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    corr_id = str(uuid.uuid4())

    mock_misses = mocker.patch.object(SSE_REDIS_BUFFER_MISSES_TOTAL, "inc")

    raw_buffer = [
        json.dumps({
            "chunk_index": 0,
            "event_type": "chunk",
            "is_final": True,
            # Missing "payload"
        }).encode("utf-8")
    ]
    mock_redis_client.lrange.return_value = raw_buffer

    events = []
    async for event in orchestrator.stream_chat(
        session_id=session_id,
        tenant_id=ws_id,
        user_id=user_id,
        query="Replay test",
        correlation_id=corr_id,
        last_event_id=f"{corr_id}:0",
    ):
        events.append(event)

    assert len(events) == 1
    assert "STREAM_EXPIRED" in events[0]
    mock_misses.assert_called_once()
    ai_wrapper.stream_request.assert_not_called()


@pytest.mark.asyncio
async def test_replay_non_dict_payload_rejected(
    orchestrator_harness, mock_redis_client, mocker
):
    """Entry where 'payload' is not a dictionary is rejected."""
    orchestrator, ai_wrapper, _, _ = orchestrator_harness
    ws_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    corr_id = str(uuid.uuid4())

    mock_misses = mocker.patch.object(SSE_REDIS_BUFFER_MISSES_TOTAL, "inc")

    raw_buffer = [
        json.dumps({
            "chunk_index": 0,
            "event_type": "chunk",
            "payload": "string-payload-not-dict",
            "is_final": True,
        }).encode("utf-8")
    ]
    mock_redis_client.lrange.return_value = raw_buffer

    events = []
    async for event in orchestrator.stream_chat(
        session_id=session_id,
        tenant_id=ws_id,
        user_id=user_id,
        query="Replay test",
        correlation_id=corr_id,
        last_event_id=f"{corr_id}:0",
    ):
        events.append(event)

    assert len(events) == 1
    assert "STREAM_EXPIRED" in events[0]
    mock_misses.assert_called_once()
    ai_wrapper.stream_request.assert_not_called()


@pytest.mark.asyncio
async def test_replay_missing_or_invalid_event_type_rejected(
    orchestrator_harness, mock_redis_client, mocker
):
    """Entry with unsupported event_type is rejected."""
    orchestrator, ai_wrapper, _, _ = orchestrator_harness
    ws_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    corr_id = str(uuid.uuid4())

    mock_misses = mocker.patch.object(SSE_REDIS_BUFFER_MISSES_TOTAL, "inc")

    raw_buffer = [
        json.dumps({
            "chunk_index": 0,
            "event_type": "unsupported_event",
            "payload": {
                "chunk_index": 0,
                "text_delta": "test",
                "is_final": True,
                "correlation_id": corr_id,
            },
            "is_final": True,
        }).encode("utf-8")
    ]
    mock_redis_client.lrange.return_value = raw_buffer

    events = []
    async for event in orchestrator.stream_chat(
        session_id=session_id,
        tenant_id=ws_id,
        user_id=user_id,
        query="Replay test",
        correlation_id=corr_id,
        last_event_id=f"{corr_id}:0",
    ):
        events.append(event)

    assert len(events) == 1
    assert "STREAM_EXPIRED" in events[0]
    mock_misses.assert_called_once()
    ai_wrapper.stream_request.assert_not_called()


@pytest.mark.asyncio
async def test_replay_boolean_chunk_index_rejected(
    orchestrator_harness, mock_redis_client, mocker
):
    """Entry with boolean chunk_index (e.g. True instead of int 0/1) is rejected."""
    orchestrator, ai_wrapper, _, _ = orchestrator_harness
    ws_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    corr_id = str(uuid.uuid4())

    mock_misses = mocker.patch.object(SSE_REDIS_BUFFER_MISSES_TOTAL, "inc")

    raw_buffer = [
        json.dumps({
            "chunk_index": True,  # Boolean masquerading as int!
            "event_type": "chunk",
            "payload": {
                "chunk_index": 0,
                "text_delta": "test",
                "is_final": True,
                "correlation_id": corr_id,
            },
            "is_final": True,
        }).encode("utf-8")
    ]
    mock_redis_client.lrange.return_value = raw_buffer

    events = []
    async for event in orchestrator.stream_chat(
        session_id=session_id,
        tenant_id=ws_id,
        user_id=user_id,
        query="Replay test",
        correlation_id=corr_id,
        last_event_id=f"{corr_id}:0",
    ):
        events.append(event)

    assert len(events) == 1
    assert "STREAM_EXPIRED" in events[0]
    mock_misses.assert_called_once()
    ai_wrapper.stream_request.assert_not_called()


@pytest.mark.asyncio
async def test_replay_negative_chunk_index_rejected(
    orchestrator_harness, mock_redis_client, mocker
):
    """Entry with negative chunk_index is rejected."""
    orchestrator, ai_wrapper, _, _ = orchestrator_harness
    ws_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    corr_id = str(uuid.uuid4())

    mock_misses = mocker.patch.object(SSE_REDIS_BUFFER_MISSES_TOTAL, "inc")

    raw_buffer = [
        json.dumps({
            "chunk_index": -1,
            "event_type": "chunk",
            "payload": {
                "chunk_index": -1,
                "text_delta": "test",
                "is_final": True,
                "correlation_id": corr_id,
            },
            "is_final": True,
        }).encode("utf-8")
    ]
    mock_redis_client.lrange.return_value = raw_buffer

    events = []
    async for event in orchestrator.stream_chat(
        session_id=session_id,
        tenant_id=ws_id,
        user_id=user_id,
        query="Replay test",
        correlation_id=corr_id,
        last_event_id=f"{corr_id}:0",
    ):
        events.append(event)

    assert len(events) == 1
    assert "STREAM_EXPIRED" in events[0]
    mock_misses.assert_called_once()
    ai_wrapper.stream_request.assert_not_called()


@pytest.mark.asyncio
async def test_replay_invalid_is_final_type_rejected(
    orchestrator_harness, mock_redis_client, mocker
):
    """Entry where is_final is an integer or non-boolean is rejected."""
    orchestrator, ai_wrapper, _, _ = orchestrator_harness
    ws_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    corr_id = str(uuid.uuid4())

    mock_misses = mocker.patch.object(SSE_REDIS_BUFFER_MISSES_TOTAL, "inc")

    raw_buffer = [
        json.dumps({
            "chunk_index": 0,
            "event_type": "chunk",
            "payload": {
                "chunk_index": 0,
                "text_delta": "test",
                "is_final": True,
                "correlation_id": corr_id,
            },
            "is_final": 1,  # Integer 1 instead of bool True!
        }).encode("utf-8")
    ]
    mock_redis_client.lrange.return_value = raw_buffer

    events = []
    async for event in orchestrator.stream_chat(
        session_id=session_id,
        tenant_id=ws_id,
        user_id=user_id,
        query="Replay test",
        correlation_id=corr_id,
        last_event_id=f"{corr_id}:0",
    ):
        events.append(event)

    assert len(events) == 1
    assert "STREAM_EXPIRED" in events[0]
    mock_misses.assert_called_once()
    ai_wrapper.stream_request.assert_not_called()


@pytest.mark.asyncio
async def test_replay_invalid_payload_fields_rejected(
    orchestrator_harness, mock_redis_client, mocker
):
    """Entry where payload violates StreamingGenerationChunkDTO schema is rejected."""
    orchestrator, ai_wrapper, _, _ = orchestrator_harness
    ws_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    corr_id = str(uuid.uuid4())

    mock_misses = mocker.patch.object(SSE_REDIS_BUFFER_MISSES_TOTAL, "inc")

    raw_buffer = [
        json.dumps({
            "chunk_index": 0,
            "event_type": "chunk",
            "payload": {
                "chunk_index": 0,
                "text_delta": 12345,  # text_delta must be str, not int!
                "is_final": True,
                "correlation_id": corr_id,
            },
            "is_final": True,
        }).encode("utf-8")
    ]
    mock_redis_client.lrange.return_value = raw_buffer

    events = []
    async for event in orchestrator.stream_chat(
        session_id=session_id,
        tenant_id=ws_id,
        user_id=user_id,
        query="Replay test",
        correlation_id=corr_id,
        last_event_id=f"{corr_id}:0",
    ):
        events.append(event)

    assert len(events) == 1
    assert "STREAM_EXPIRED" in events[0]
    mock_misses.assert_called_once()
    ai_wrapper.stream_request.assert_not_called()


@pytest.mark.asyncio
async def test_replay_malformed_entry_later_in_buffer_yields_zero_chunks(
    orchestrator_harness, mock_redis_client, mocker
):
    """When a malformed chunk exists later in buffer, no earlier chunk is replayed before validation finishes."""
    orchestrator, ai_wrapper, _, _ = orchestrator_harness
    ws_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    corr_id = str(uuid.uuid4())

    mock_misses = mocker.patch.object(SSE_REDIS_BUFFER_MISSES_TOTAL, "inc")
    mock_replayed = mocker.patch.object(SSE_REPLAYED_CHUNKS_TOTAL, "inc")

    # Chunk 0 and 1 are perfectly valid, but Chunk 2 is corrupted (missing payload)
    raw_buffer = [
        json.dumps({
            "chunk_index": 0,
            "event_type": "chunk",
            "payload": {
                "chunk_index": 0,
                "text_delta": "Part 0",
                "citations_delta": [],
                "is_final": False,
                "correlation_id": corr_id,
            },
            "is_final": False,
        }).encode("utf-8"),
        json.dumps({
            "chunk_index": 1,
            "event_type": "chunk",
            "payload": {
                "chunk_index": 1,
                "text_delta": "Part 1",
                "citations_delta": [],
                "is_final": False,
                "correlation_id": corr_id,
            },
            "is_final": False,
        }).encode("utf-8"),
        json.dumps({
            "chunk_index": 2,
            "event_type": "chunk",
            # Missing payload entirely
            "is_final": True,
        }).encode("utf-8"),
    ]
    mock_redis_client.lrange.return_value = raw_buffer

    # Client asks for chunks > 0 (Chunk 1 would qualify if validated eagerly)
    last_event_id = f"{corr_id}:0"

    events = []
    async for event in orchestrator.stream_chat(
        session_id=session_id,
        tenant_id=ws_id,
        user_id=user_id,
        query="Replay test",
        correlation_id=corr_id,
        last_event_id=last_event_id,
    ):
        events.append(event)

    # Must contain ONLY the error event, and zero replayed data chunks!
    assert len(events) == 1
    assert "STREAM_EXPIRED" in events[0]
    assert "Part 1" not in events[0]
    mock_replayed.assert_not_called()
    mock_misses.assert_called_once()
    ai_wrapper.stream_request.assert_not_called()


@pytest.mark.asyncio
async def test_replay_empty_buffer_miss(
    orchestrator_harness, mock_redis_client, mocker
):
    """Empty Redis buffer increments buffer misses and emits STREAM_EXPIRED."""
    orchestrator, ai_wrapper, _, _ = orchestrator_harness
    ws_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    corr_id = str(uuid.uuid4())

    mock_misses = mocker.patch.object(SSE_REDIS_BUFFER_MISSES_TOTAL, "inc")
    mock_hits = mocker.patch.object(SSE_REDIS_BUFFER_HITS_TOTAL, "inc")

    mock_redis_client.lrange.return_value = []

    events = []
    async for event in orchestrator.stream_chat(
        session_id=session_id,
        tenant_id=ws_id,
        user_id=user_id,
        query="Replay test",
        correlation_id=corr_id,
        last_event_id=f"{corr_id}:0",
    ):
        events.append(event)

    assert len(events) == 1
    assert "STREAM_EXPIRED" in events[0]
    mock_misses.assert_called_once()
    mock_hits.assert_not_called()
    ai_wrapper.stream_request.assert_not_called()


@pytest.mark.asyncio
async def test_replay_redis_connection_failure_telemetry(
    orchestrator_harness, mock_redis_client, mocker
):
    """When Redis fails on lrange with RedisError, STREAM_EXPIRED is emitted but misses total is NOT incremented."""
    orchestrator, ai_wrapper, _, _ = orchestrator_harness
    ws_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    corr_id = str(uuid.uuid4())

    mock_misses = mocker.patch.object(SSE_REDIS_BUFFER_MISSES_TOTAL, "inc")
    mock_hits = mocker.patch.object(SSE_REDIS_BUFFER_HITS_TOTAL, "inc")
    mock_active = mocker.patch.object(SSE_ACTIVE_STREAMS, "dec")

    # Redis read exception using RedisConnectionError (subclass of RedisError)
    mock_redis_client.lrange.side_effect = RedisConnectionError("Redis read timeout")

    events = []
    async for event in orchestrator.stream_chat(
        session_id=session_id,
        tenant_id=ws_id,
        user_id=user_id,
        query="Replay test",
        correlation_id=corr_id,
        last_event_id=f"{corr_id}:0",
    ):
        events.append(event)

    assert len(events) == 1
    assert "STREAM_EXPIRED" in events[0]
    # Telemetry isolation: Redis read error is NOT a cache miss
    mock_misses.assert_not_called()
    mock_hits.assert_not_called()
    mock_active.assert_called_once()
    ai_wrapper.stream_request.assert_not_called()


@pytest.mark.asyncio
async def test_unexpected_non_redis_read_exception_propagates(
    orchestrator_harness, mock_redis_client
):
    """Unexpected non-Redis exception during replay lrange must NOT be swallowed as a Redis failure."""
    orchestrator, ai_wrapper, _, _ = orchestrator_harness
    ws_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    corr_id = str(uuid.uuid4())

    mock_redis_client.lrange.side_effect = RuntimeError("Simulated internal runtime bug")

    with pytest.raises(RuntimeError, match="Simulated internal runtime bug"):
        async for _ in orchestrator.stream_chat(
            session_id=session_id,
            tenant_id=ws_id,
            user_id=user_id,
            query="Replay test",
            correlation_id=corr_id,
            last_event_id=f"{corr_id}:0",
        ):
            pass


@pytest.mark.asyncio
async def test_replay_invalid_correlation_id(
    orchestrator_harness, mock_redis_client, mocker
):
    """When Last-Event-ID has wrong correlation ID, INVALID_CORRELATION error is emitted."""
    orchestrator, ai_wrapper, _, _ = orchestrator_harness
    ws_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    corr_id = str(uuid.uuid4())

    mock_active = mocker.patch.object(SSE_ACTIVE_STREAMS, "dec")

    events = []
    async for event in orchestrator.stream_chat(
        session_id=session_id,
        tenant_id=ws_id,
        user_id=user_id,
        query="Replay test",
        correlation_id=corr_id,
        last_event_id="wrong-corr-id:0",
    ):
        events.append(event)

    assert len(events) == 1
    assert "INVALID_CORRELATION" in events[0]
    mock_active.assert_called_once()
    ai_wrapper.stream_request.assert_not_called()
