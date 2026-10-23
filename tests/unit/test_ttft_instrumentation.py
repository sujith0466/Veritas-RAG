"""Unit tests for REC-005: TTFT Instrumentation (Time-To-First-Token).

Ensures deterministic measurement of TTFT in ChatOrchestrator without
global clock pollution, verifies zero dynamic labels, zero noise, and
proper isolation from the global Prometheus registry.
"""

import asyncio
import json
import uuid
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient
import pytest

from backend.main import app
from backend.models.entities.workspace_member import MemberStatus, WorkspaceMember
from backend.modules.chat.models.chat_session import ChatSession
from backend.modules.chat.services.chat_orchestrator import ChatOrchestrator
from backend.modules.generation.schemas.generation_dto import StreamingGenerationChunkDTO
from backend.document.models.document import Document
from backend.observability.metrics.prometheus import SSE_TTFT_SECONDS


class MonotonicClockFixture:
    """Deterministic monotonic clock fixture allowing tests to control simulated time."""

    def __init__(self, initial_time: float = 100.0) -> None:
        self.current_time = initial_time

    def tick(self, seconds: float) -> float:
        self.current_time += seconds
        return self.current_time

    def __call__(self) -> float:
        return self.current_time


@pytest.fixture
def mock_clock(mocker) -> MonotonicClockFixture:
    """Patch time.perf_counter strictly within chat_orchestrator module scope."""
    clock = MonotonicClockFixture(initial_time=100.0)
    mocker.patch(
        "backend.modules.chat.services.chat_orchestrator.time.perf_counter",
        side_effect=clock,
    )
    return clock


@pytest.fixture
def mock_ttft_observer(mocker):
    """Isolate SSE_TTFT_SECONDS observer directly, preventing global registry pollution."""
    return mocker.patch.object(SSE_TTFT_SECONDS, "observe")


@pytest.fixture
def mock_redis(mocker):
    """Mock Redis client for SSE replay and buffering."""
    redis_mock = AsyncMock()
    redis_mock.lrange = AsyncMock(return_value=[])
    redis_mock.rpush = AsyncMock()
    redis_mock.expire = AsyncMock()
    mocker.patch(
        "backend.modules.chat.services.chat_orchestrator.get_redis_client",
        return_value=redis_mock,
    )
    return redis_mock


@pytest.fixture
def orchestrator_harness(mocker, mock_redis):
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
        has_processing_doc: bool = False,
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
        fake_proc_doc = MagicMock(spec=Document) if has_processing_doc else None

        async def _execute(statement, *args, **kwargs):
            stmt_str = str(statement)
            res = MagicMock()
            if "chat_sessions" in stmt_str:
                res.scalar_one_or_none.return_value = fake_session
            elif "workspace_members" in stmt_str:
                res.scalar_one_or_none.return_value = fake_member
            elif "documents" in stmt_str:
                if "status = :status_1" in stmt_str or "READY" in stmt_str:
                    res.scalar_one_or_none.return_value = fake_ready_doc
                else:
                    res.scalar_one_or_none.return_value = fake_proc_doc
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
async def test_ttft_observed_on_first_text_chunk(
    mock_clock, mock_ttft_observer, orchestrator_harness
):
    """Observation is anchor-bound to the arrival of the first non-empty text chunk."""
    orchestrator, ai_wrapper, configure_db, _ = orchestrator_harness
    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    ws_id = str(uuid.uuid4())
    corr_id = str(uuid.uuid4())

    configure_db(user_id, session_id, ws_id, has_ready_doc=True)

    async def mock_stream(*args, **kwargs):
        # Initial elapsed before token 0: 2.35s
        mock_clock.tick(2.35)
        yield StreamingGenerationChunkDTO(
            chunk_index=0,
            text_delta="Hello",
            citations_delta=[],
            is_final=False,
            correlation_id=corr_id,
        )
        mock_clock.tick(1.65)
        yield StreamingGenerationChunkDTO(
            chunk_index=1,
            text_delta=" world!",
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
        query="Hello",
        correlation_id=corr_id,
    ):
        events.append(event)

    assert len(events) >= 2
    mock_ttft_observer.assert_called_once_with(pytest.approx(2.35))


@pytest.mark.asyncio
async def test_ttft_observed_strictly_once_across_multiple_chunks(
    mock_clock, mock_ttft_observer, orchestrator_harness
):
    """Exactly-once observation guard holds across multi-token streams."""
    orchestrator, ai_wrapper, configure_db, _ = orchestrator_harness
    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    ws_id = str(uuid.uuid4())
    corr_id = str(uuid.uuid4())

    configure_db(user_id, session_id, ws_id, has_ready_doc=True)

    async def mock_stream(*args, **kwargs):
        mock_clock.tick(1.50)
        for i in range(15):
            mock_clock.tick(0.05)
            yield StreamingGenerationChunkDTO(
                chunk_index=i,
                text_delta=f"chunk_{i} ",
                citations_delta=[],
                is_final=(i == 14),
                is_fully_grounded=True,
                correlation_id=corr_id,
            )

    ai_wrapper.stream_request.return_value = mock_stream()

    events = []
    async for event in orchestrator.stream_chat(
        session_id=session_id,
        tenant_id=ws_id,
        user_id=user_id,
        query="Stream test",
        correlation_id=corr_id,
    ):
        events.append(event)

    assert mock_ttft_observer.call_count == 1
    # First chunk observed at 1.50 + 0.05 = 1.55s
    mock_ttft_observer.assert_called_once_with(pytest.approx(1.55))


@pytest.mark.asyncio
async def test_ttft_deferred_until_non_empty_text_chunk(
    mock_clock, mock_ttft_observer, orchestrator_harness
):
    """Leading empty or metadata-only chunks defer observation until real text arrives."""
    orchestrator, ai_wrapper, configure_db, _ = orchestrator_harness
    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    ws_id = str(uuid.uuid4())
    corr_id = str(uuid.uuid4())

    configure_db(user_id, session_id, ws_id, has_ready_doc=True)

    async def mock_stream(*args, **kwargs):
        # Leading metadata/status chunk with empty text delta
        mock_clock.tick(0.80)
        yield StreamingGenerationChunkDTO(
            chunk_index=0,
            text_delta="",
            citations_delta=[],
            is_final=False,
            correlation_id=corr_id,
            wrapper_metadata={"stage": "retrieval_complete"},
        )
        # Second chunk delivers genuine text
        mock_clock.tick(1.70)
        yield StreamingGenerationChunkDTO(
            chunk_index=1,
            text_delta="Here is the factual summary",
            citations_delta=[],
            is_final=False,
            correlation_id=corr_id,
        )
        # Final punctuation chunk
        mock_clock.tick(0.50)
        yield StreamingGenerationChunkDTO(
            chunk_index=2,
            text_delta=".",
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
        query="Summary test",
        correlation_id=corr_id,
    ):
        events.append(event)

    # Observation must occur at 0.80 + 1.70 = 2.50s (arrival of chunk 1)
    mock_ttft_observer.assert_called_once_with(pytest.approx(2.50))


@pytest.mark.asyncio
async def test_ttft_not_observed_on_pre_token_error(
    mock_clock, mock_ttft_observer, orchestrator_harness
):
    """Pre-token session verification errors yield error event without observing TTFT."""
    orchestrator, _, configure_db, session_mock = orchestrator_harness
    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    ws_id = str(uuid.uuid4())
    corr_id = str(uuid.uuid4())

    # Session not found
    async def _execute_empty(statement, *args, **kwargs):
        res = MagicMock()
        res.scalar_one_or_none.return_value = None
        return res

    session_mock.execute.side_effect = _execute_empty

    events = []
    async for event in orchestrator.stream_chat(
        session_id=session_id,
        tenant_id=ws_id,
        user_id=user_id,
        query="Hello",
        correlation_id=corr_id,
    ):
        events.append(event)

    assert len(events) == 1
    assert "SESSION_ACCESS_DENIED" in events[0]
    mock_ttft_observer.assert_not_called()


@pytest.mark.asyncio
async def test_ttft_not_observed_on_client_cancellation_before_token(
    mock_clock, mock_ttft_observer, orchestrator_harness
):
    """Client abort prior to token 0 rethrows CancelledError without observing TTFT."""
    orchestrator, ai_wrapper, configure_db, _ = orchestrator_harness
    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    ws_id = str(uuid.uuid4())
    corr_id = str(uuid.uuid4())

    configure_db(user_id, session_id, ws_id, has_ready_doc=True)

    async def mock_stream(*args, **kwargs):
        mock_clock.tick(1.00)
        raise asyncio.CancelledError("Client disconnected before generation")
        yield None  # Unreachable

    ai_wrapper.stream_request.return_value = mock_stream()

    with pytest.raises(asyncio.CancelledError):
        async for _ in orchestrator.stream_chat(
            session_id=session_id,
            tenant_id=ws_id,
            user_id=user_id,
            query="Hello",
            correlation_id=corr_id,
        ):
            pass

    mock_ttft_observer.assert_not_called()


@pytest.mark.asyncio
async def test_ttft_not_observed_on_empty_generation(
    mock_clock, mock_ttft_observer, orchestrator_harness
):
    """Empty generation without any chunks exits gracefully without observing TTFT."""
    orchestrator, ai_wrapper, configure_db, _ = orchestrator_harness
    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    ws_id = str(uuid.uuid4())
    corr_id = str(uuid.uuid4())

    configure_db(user_id, session_id, ws_id, has_ready_doc=True)

    async def empty_stream(*args, **kwargs):
        if False:
            yield None

    ai_wrapper.stream_request.return_value = empty_stream()

    events = []
    async for event in orchestrator.stream_chat(
        session_id=session_id,
        tenant_id=ws_id,
        user_id=user_id,
        query="Hello",
        correlation_id=corr_id,
    ):
        events.append(event)

    mock_ttft_observer.assert_not_called()


@pytest.mark.asyncio
async def test_ttft_not_observed_on_kb_indexing_fallback(
    mock_clock, mock_ttft_observer, orchestrator_harness
):
    """System fallback messages during KB indexing bypass generation and do not observe TTFT."""
    orchestrator, ai_wrapper, configure_db, _ = orchestrator_harness
    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    ws_id = str(uuid.uuid4())
    corr_id = str(uuid.uuid4())

    # Knowledge base in progress, no ready docs
    configure_db(user_id, session_id, ws_id, has_ready_doc=False, has_processing_doc=True)

    events = []
    async for event in orchestrator.stream_chat(
        session_id=session_id,
        tenant_id=ws_id,
        user_id=user_id,
        query="Hello",
        correlation_id=corr_id,
    ):
        events.append(event)

    assert len(events) in (1, 2)
    assert "Your knowledge base is currently being prepared" in events[0]
    if len(events) == 2:
        assert "event: done" in events[1]
    ai_wrapper.stream_request.assert_not_called()
    mock_ttft_observer.assert_not_called()


@pytest.mark.asyncio
async def test_ttft_cancellation_after_first_token_retains_single_observation(
    mock_clock, mock_ttft_observer, orchestrator_harness
):
    """Client abort occurring after token 0 preserves the single recorded TTFT observation."""
    orchestrator, ai_wrapper, configure_db, _ = orchestrator_harness
    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    ws_id = str(uuid.uuid4())
    corr_id = str(uuid.uuid4())

    configure_db(user_id, session_id, ws_id, has_ready_doc=True)

    async def mock_stream(*args, **kwargs):
        mock_clock.tick(1.80)
        yield StreamingGenerationChunkDTO(
            chunk_index=0,
            text_delta="Initial chunk",
            citations_delta=[],
            is_final=False,
            correlation_id=corr_id,
        )
        mock_clock.tick(0.40)
        raise asyncio.CancelledError("Client disconnected mid-stream")

    ai_wrapper.stream_request.return_value = mock_stream()

    with pytest.raises(asyncio.CancelledError):
        async for _ in orchestrator.stream_chat(
            session_id=session_id,
            tenant_id=ws_id,
            user_id=user_id,
            query="Hello",
            correlation_id=corr_id,
        ):
            pass

    mock_ttft_observer.assert_called_once_with(pytest.approx(1.80))


def test_metrics_scrape_endpoint_empirical_verification():
    """Verify live scrape endpoints expose raguard_sse_ttft_seconds_bucket."""
    client = TestClient(app)

    # 1. Root /metrics endpoint
    res_root = client.get("/metrics")
    assert res_root.status_code == 200
    assert "raguard_sse_ttft_seconds_bucket" in res_root.text

    # 2. Canonical /api/v1/metrics endpoint
    res_v1 = client.get("/api/v1/metrics")
    assert res_v1.status_code == 200
    assert "raguard_sse_ttft_seconds_bucket" in res_v1.text
