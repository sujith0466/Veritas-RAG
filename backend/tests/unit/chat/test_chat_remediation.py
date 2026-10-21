"""Unit tests verifying Phase 5 WP-CHAT remediation.

Findings covered:
- CHAT-001: Client-Side Message ID Desync Breaks Feedback/Rewind
- CHAT-002: Multi-Turn Message Pagination Ordering Inversion
- CHAT-003: 0 Ready Documents Yields Internal Error Masked as 500
- CHAT-004: Fire-and-Forget Persistence and Token Misattribution
- CHAT-005: LLM Streaming Exceptions Swallowed as Success Responses
- CHAT-006: Non-Alternating Conversation History Triggers Gemini 400
- SSE-001: Mid-Stream SSE Recovery Rejects Active Streams as STREAM_EXPIRED
- SSE-002: SSE Event Type Fragmentation: Schema Defines 14, Emits 5
- SSE-003: Navigation State Race Condition Triggers Duplicate Streams
- SCORE-001: Dead Code: compute_chat_reliability_score Never Invoked
- SCORE-002: Indexing Waiting Message Assigned False 1.0 Reliability Score
- SCORE-003: Multi-Token Hallucinated Citation Markers Leak into Stream
- OBS-002: Missing TTFT Instrumentation on Standard Completions
"""

import asyncio
import json
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.ai.interfaces.llm_provider import LLMRequest
from backend.ai.providers.gemini import GeminiProvider
from backend.ai.wrapper.service import WorkspaceValidationError
from backend.api.v1.schemas.sse import SSEEventType, SSEMessageDTO
from backend.modules.chat.models.chat_message import ChatMessage
from backend.modules.chat.repositories.chat_repository import ChatRepository
from backend.modules.chat.services.chat_orchestrator import (
    ChatOrchestrator,
    compute_chat_reliability_score,
)
from backend.modules.generation.schemas.generation_dto import (
    CitationDTO,
    GenerationRequestDTO,
    GenerationRequestDTOv2,
    GroundedAnswerDTO,
    PromptGuardrailConfigDTO,
    StreamingGenerationChunkDTO,
)
from backend.modules.generation.services.citation_extractor import CitationExtractor
from backend.modules.generation.services.generation_service import (
    GroundedGenerationService,
)
from backend.modules.generation.services.streaming_generation_service import (
    StreamingGroundedGenerationService,
)
from backend.modules.retrieval.schemas.retrieval_dto import RankedEvidenceDTO


def make_ranked_evidence(
    chunk_id: str | None = None,
    content: str = "Test evidence content",
    doc_id: str | None = None,
    version_id: str | None = None,
    tenant_id: str | None = None,
    rank: int = 1,
) -> RankedEvidenceDTO:
    return RankedEvidenceDTO(
        chunk_id=chunk_id or str(uuid.uuid4()),
        document_id=doc_id or str(uuid.uuid4()),
        document_version_id=version_id or str(uuid.uuid4()),
        tenant_id=tenant_id or str(uuid.uuid4()),
        content=content,
        compressed_content=None,
        compression_ratio=1.0,
        dense_rank=1,
        sparse_rank=1,
        rrf_score=0.9,
        raw_rerank_score=0.9,
        normalized_relevance_score=0.9,
        final_rank=rank,
        matched_sources=["dense"],
        metadata={},
    )


# ==============================================================================
# CHAT-006: Gemini non-alternating conversation turns
# ==============================================================================
class TestGeminiAlternatingTurns:
    """CHAT-006: Ensure consecutive same-role turns are merged into strictly alternating turns."""

    def test_build_contents_merges_consecutive_user_turns(self):
        with patch("backend.ai.providers.gemini.get_settings") as mock_settings, \
             patch("backend.ai.providers.gemini.genai"):
            mock_settings.return_value.gemini.api_key = "test"
            mock_settings.return_value.gemini.model = "gemini-1.5-flash"
            mock_settings.return_value.gemini.lite_model = "gemini-1.5-flash-8b"
            mock_settings.return_value.gemini.temperature = 0.7
            mock_settings.return_value.gemini.max_output_tokens = 1000

            provider = GeminiProvider()
            req = LLMRequest(
                prompt="Follow up question",
                system_instruction="You are a helpful assistant.",
                conversation_history=[
                    {"role": "user", "content": "First user turn"},
                    {"role": "user", "content": "Second user turn"},
                    {"role": "assistant", "content": "First model reply"},
                ],
            )
            contents = provider._build_contents(req)

            assert isinstance(contents, list)
            for i in range(len(contents) - 1):
                assert contents[i]["role"] != contents[i + 1]["role"], (
                    f"Turns at {i} and {i+1} have the same role: {contents[i]['role']}"
                )

            assert contents[0]["role"] == "user"
            assert "First user turn" in contents[0]["parts"][0]
            assert "Second user turn" in contents[0]["parts"][0]
            assert contents[1]["role"] == "model"
            assert "First model reply" in contents[1]["parts"][0]
            assert contents[2]["role"] == "user"
            assert "Follow up question" in contents[2]["parts"][0]

    def test_build_contents_merges_consecutive_model_turns(self):
        with patch("backend.ai.providers.gemini.get_settings") as mock_settings, \
             patch("backend.ai.providers.gemini.genai"):
            mock_settings.return_value.gemini.api_key = "test"
            mock_settings.return_value.gemini.model = "gemini-1.5-flash"
            mock_settings.return_value.gemini.lite_model = "gemini-1.5-flash-8b"
            mock_settings.return_value.gemini.temperature = 0.7
            mock_settings.return_value.gemini.max_output_tokens = 1000

            provider = GeminiProvider()
            req = LLMRequest(
                prompt="User query",
                system_instruction=None,
                conversation_history=[
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Part 1 of model answer"},
                    {"role": "assistant", "content": "Part 2 of model answer"},
                ],
            )
            contents = provider._build_contents(req)

            assert len(contents) == 3
            assert contents[0]["role"] == "user"
            assert contents[1]["role"] == "model"
            assert "Part 1 of model answer" in contents[1]["parts"][0]
            assert "Part 2 of model answer" in contents[1]["parts"][0]
            assert contents[2]["role"] == "user"
            assert "User query" in contents[2]["parts"][0]


# ==============================================================================
# SSE-002: SSE Event Type Consolidation
# ==============================================================================
class TestSSEEventTypeSchema:
    """SSE-002: Ensure schema defines the 5 canonical emitted event types."""

    def test_sse_event_type_members(self):
        from typing import get_args
        allowed = set(get_args(SSEEventType))
        expected = {"chunk", "progress", "done", "error", "heartbeat"}
        assert allowed == expected

    def test_sse_message_dto_serialization(self):
        dto = SSEMessageDTO(
            id="test-cor-1",
            event="chunk",
            data='{"text_delta": "hello"}'
        )
        serialized = dto.to_sse_string()
        assert "event: chunk\n" in serialized
        assert "id: test-cor-1\n" in serialized
        assert 'data: {"text_delta": "hello"}\n\n' in serialized


# ==============================================================================
# CHAT-002: Pagination order in repository
# ==============================================================================
class TestChatPaginationOrdering:
    """CHAT-002: Messages ordered by created_at.desc() in repository query."""

    @pytest.mark.asyncio
    async def test_list_messages_orders_desc(self):
        mock_session = AsyncMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = ChatRepository(mock_session)
        repo.get_session = AsyncMock(return_value=MagicMock())

        await repo.list_messages(
            session_id=str(uuid.uuid4()),
            tenant_id=str(uuid.uuid4()),
            user_id=str(uuid.uuid4()),
            limit=50,
            offset=0
        )

        assert mock_session.execute.called
        call_args = mock_session.execute.call_args[0][0]
        sql_text = str(call_args)
        assert "DESC" in sql_text.upper()

    @pytest.mark.asyncio
    async def test_list_messages_orders_desc_with_id_tiebreaker(self):
        """CHAT-002: Ensure list_messages applies (created_at.desc(), id.desc()) for deterministic ordering."""
        mock_session = AsyncMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = ChatRepository(mock_session)
        repo.get_session = AsyncMock(return_value=MagicMock())

        await repo.list_messages(
            session_id=str(uuid.uuid4()),
            tenant_id=str(uuid.uuid4()),
            user_id=str(uuid.uuid4()),
            limit=50,
            offset=0
        )

        assert mock_session.execute.called
        select_stmt = mock_session.execute.call_args[0][0]
        order_clauses = select_stmt._order_by_clauses
        assert len(order_clauses) == 2
        assert "created_at" in str(order_clauses[0]).lower()
        assert "id" in str(order_clauses[1]).lower()


# ==============================================================================
# SCORE-001 & SCORE-002: Reliability score computation and waiting message
# ==============================================================================
class TestReliabilityScoring:
    """SCORE-001 & SCORE-002: Connect dead code & waiting message score."""

    def test_compute_chat_reliability_score_grounded(self):
        answer = "Antigravity is a fast agentic assistant. [1]"
        evidence = [{"content": "Antigravity is a fast agentic assistant."}]
        citations = [{"citation_index": 1, "relevance_score": 1.0}]

        score = compute_chat_reliability_score(
            answer_text=answer,
            evidence_chunks=evidence,
            citations=citations,
            is_grounded=True
        )
        assert 0.0 <= score <= 1.0
        assert score > 0.5

    def test_compute_chat_reliability_score_empty_answer(self):
        score = compute_chat_reliability_score(
            answer_text="",
            evidence_chunks=[],
            citations=[],
            is_grounded=False
        )
        assert score == 0.0


# ==============================================================================
# SCORE-003: Lookahead buffering for partial citation markers
# ==============================================================================
class TestStreamingCitationLookahead:
    """SCORE-003: Multi-token hallucinated citation markers leak into stream."""

    @pytest.mark.asyncio
    async def test_citation_lookahead_buffers_split_bracket(self):
        class MockSplitStreamProvider:
            async def stream(self, req):
                yield "The facts are clear ["
                yield "1"
                yield "]. End of claim."

        safe_chunks = [make_ranked_evidence(content="The facts are clear.")]
        extractor = CitationExtractor()
        service = StreamingGroundedGenerationService(
            citation_extractor=extractor,
            llm_provider=MockSplitStreamProvider()
        )

        req = GenerationRequestDTOv2(
            query="test",
            evidence_chunks=safe_chunks,
            correlation_id="test-corr",
            tenant_id="tenant-1",
            guardrail_config=PromptGuardrailConfigDTO()
        )

        chunks = []
        async for chunk in service.generate_stream(req):
            chunks.append(chunk)

        for c in chunks[:-1]:
            if c.text_delta:
                assert not c.text_delta.endswith("["), f"Chunk leaked open bracket: {c.text_delta}"

    @pytest.mark.asyncio
    async def test_hallucinated_citation_scrubbed_across_split_tokens(self):
        class MockHallucinatedStreamProvider:
            async def stream(self, req):
                yield "This fact is unverified ["
                yield "99"
                yield "]. End of sentence."

        safe_chunks = [make_ranked_evidence(content="Only chunk one exists.")]
        extractor = CitationExtractor()
        service = StreamingGroundedGenerationService(
            citation_extractor=extractor,
            llm_provider=MockHallucinatedStreamProvider()
        )

        req = GenerationRequestDTOv2(
            query="test",
            evidence_chunks=safe_chunks,
            correlation_id="test-corr",
            tenant_id="tenant-1",
            guardrail_config=PromptGuardrailConfigDTO()
        )

        emitted_text = ""
        async for chunk in service.generate_stream(req):
            emitted_text += chunk.text_delta

        assert "[99]" not in emitted_text
        assert "This fact is unverified" in emitted_text


# ==============================================================================
# CHAT-005: LLM Streaming Exceptions Swallowed as Success Responses
# ==============================================================================
class TestStreamingExceptionPropagation:
    """CHAT-005: Re-raise exceptions to orchestrator; do not yield as assistant text."""

    @pytest.mark.asyncio
    async def test_llm_stream_exception_raises(self):
        class FailingStreamProvider:
            async def stream(self, req):
                yield "Partial response "
                raise RuntimeError("OpenAI rate limit exceeded")

        extractor = CitationExtractor()
        service = StreamingGroundedGenerationService(
            citation_extractor=extractor,
            llm_provider=FailingStreamProvider()
        )

        req = GenerationRequestDTOv2(
            query="test",
            evidence_chunks=[make_ranked_evidence(content="Evidence")],
            correlation_id="test-corr",
            tenant_id="tenant-1",
            guardrail_config=PromptGuardrailConfigDTO()
        )

        with pytest.raises(RuntimeError) as exc_info:
            async for _ in service.generate_stream(req):
                pass
        assert "OpenAI rate limit exceeded" in str(exc_info.value)


# ==============================================================================
# OBS-002: TTFT Instrumentation on Standard Completions
# ==============================================================================
class TestTTFTInstrumentation:
    """OBS-002: Measure and report ttft_ms on non-streaming GroundedAnswerDTO."""

    def test_non_streaming_ttft_ms_populated(self):
        class MockSyncLLMProvider:
            def generate(self, prompt, max_tokens):
                import time
                time.sleep(0.01)
                return "The result is grounded. [1]"

        extractor = CitationExtractor()
        service = GroundedGenerationService(
            citation_extractor=extractor,
            llm_provider=MockSyncLLMProvider()
        )

        req = GenerationRequestDTO(
            query="test query",
            evidence_chunks=[{"id": "c1", "content": "The result is grounded.", "document_id": "d1"}],
            correlation_id="cor-1"
        )

        answer = service.generate(req)
        assert isinstance(answer, GroundedAnswerDTO)
        assert answer.ttft_ms is not None
        assert answer.ttft_ms >= 5.0


# ==============================================================================
# SSE-001: Active stream replay acceptance
# ==============================================================================
class TestSSEActiveStreamRecovery:
    """SSE-001: Mid-stream recovery accepts active streams with is_final=False."""

    @pytest.mark.asyncio
    async def test_active_stream_replayed_without_expired_error(self):
        mock_redis = AsyncMock()
        chunk0 = {
            "chunk_index": 0,
            "event_type": "chunk",
            "payload": {
                "chunk_index": 0,
                "text_delta": "Hello ",
                "citations_delta": [],
                "is_final": False,
                "correlation_id": "cor-1"
            },
            "is_final": False
        }
        chunk1 = {
            "chunk_index": 1,
            "event_type": "chunk",
            "payload": {
                "chunk_index": 1,
                "text_delta": "world",
                "citations_delta": [],
                "is_final": False,
                "correlation_id": "cor-1"
            },
            "is_final": False
        }
        mock_redis.lrange = AsyncMock(return_value=[json.dumps(chunk0), json.dumps(chunk1)])

        orchestrator = ChatOrchestrator(
            ai_wrapper_service=MagicMock(),
            chat_repo=MagicMock()
        )

        test_tenant_id = str(uuid.uuid4())
        test_session_id = str(uuid.uuid4())
        test_user_id = str(uuid.uuid4())

        emitted_events = []
        with patch("backend.modules.chat.services.chat_orchestrator.get_redis_client", return_value=mock_redis):
            async for sse_line in orchestrator.stream_chat(
                session_id=test_session_id,
                tenant_id=test_tenant_id,
                user_id=test_user_id,
                query="test",
                last_event_id="cor-1:0",
                correlation_id="cor-1"
            ):
                emitted_events.append(sse_line)

        full_output = "".join(emitted_events)
        assert "STREAM_EXPIRED" not in full_output
        assert "id: cor-1:1" in full_output
        assert "world" in full_output


# ==============================================================================
# CHAT-003: 0 Ready Documents yields structured guidance without 500
# ==============================================================================
class TestZeroReadyDocumentsGuidance:
    """CHAT-003: Preflight gracefully returns structured guidance when 0 docs are ready."""

    @pytest.mark.asyncio
    async def test_zero_ready_docs_returns_guidance_chunk(self):
        orchestrator = ChatOrchestrator(
            ai_wrapper_service=MagicMock(),
            chat_repo=MagicMock()
        )

        # Mock DB session where no documents exist
        mock_db_session = AsyncMock()
        mock_scalar_result = MagicMock()
        mock_scalar_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_scalar_result)

        test_tenant_id = str(uuid.uuid4())
        test_user_id = str(uuid.uuid4())
        test_session_id = str(uuid.uuid4())

        # Mock chat session lookup
        fake_chat_session = MagicMock()
        fake_chat_session.user_id = test_user_id
        fake_chat_session.tenant_id = test_tenant_id

        def mock_execute_side_effect(stmt):
            sql = str(stmt).lower()
            res = MagicMock()
            if "chat_session" in sql or "chatsession" in sql:
                res.scalar_one_or_none.return_value = fake_chat_session
            elif "workspacemember" in sql or "workspace_member" in sql:
                res.scalar_one_or_none.return_value = uuid.UUID(test_user_id)
            elif "document" in sql:
                res.scalar_one_or_none.return_value = None  # 0 ready docs, 0 processing docs
            else:
                res.scalar_one_or_none.return_value = None
            return res

        mock_db_session.execute.side_effect = mock_execute_side_effect

        class SessionContext:
            async def __aenter__(self):
                return mock_db_session
            async def __aexit__(self, *args):
                pass

        session_factory_mock = MagicMock(return_value=SessionContext())

        emitted_events = []
        with patch("backend.modules.chat.services.chat_orchestrator.get_redis_client", return_value=None), \
             patch("backend.modules.chat.services.chat_orchestrator.get_session_factory", return_value=session_factory_mock), \
             patch("backend.modules.chat.services.chat_orchestrator.ChatRepository") as mock_repo_cls:
            mock_repo_inst = MagicMock()
            mock_repo_inst.list_messages = AsyncMock(return_value=[])
            mock_repo_inst.add_message = AsyncMock()
            mock_repo_cls.return_value = mock_repo_inst

            async for sse_line in orchestrator.stream_chat(
                session_id=test_session_id,
                tenant_id=test_tenant_id,
                user_id=test_user_id,
                query="Hello",
                correlation_id="cor-empty-docs"
            ):
                emitted_events.append(sse_line)

        full_output = "".join(emitted_events)
        assert "INTERNAL_ERROR" not in full_output
        assert "No documents have been uploaded to your knowledge base yet" in full_output
        assert "event: done" in full_output

        # Verify message persisted with 0.0 reliability score (SCORE-002)
        assert mock_repo_inst.add_message.called
        persisted_dto = mock_repo_inst.add_message.call_args[1]["dto"]
        assert persisted_dto.reliability_score == 0.0
        assert persisted_dto.metadata_json == {"system_message": True}


# ==============================================================================
# CHAT-004: Token Attribution & Persistence Timeout Handling
# ==============================================================================
class TestChat004PersistenceAndTokenAttribution:
    """CHAT-004: Verify provider-reported token usage, fallback estimates, and persistence timeout handling."""

    @pytest.mark.asyncio
    async def test_chat_004_provider_token_usage_preferred(self):
        """CHAT-004: Provider-reported usage is passed to QuotaGovernor when present."""
        test_tenant_id = str(uuid.uuid4())
        test_user_id = str(uuid.uuid4())
        test_session_id = str(uuid.uuid4())
        test_ws_id = uuid.uuid4()

        mock_wrapper = MagicMock()
        async def fake_stream_req(req, user_id=None, correlation_id=None):
            yield StreamingGenerationChunkDTO(
                chunk_index=0,
                text_delta="This is the answer.",
                is_final=True,
                correlation_id=correlation_id,
                wrapper_metadata={
                    "usage": {"prompt_tokens": 55, "completion_tokens": 120},
                    "reliability_score": 0.95
                }
            )
        mock_wrapper.stream_request = fake_stream_req

        orchestrator = ChatOrchestrator(
            ai_wrapper_service=mock_wrapper,
            chat_repo=MagicMock()
        )

        mock_db_session = AsyncMock()
        fake_chat_session = MagicMock()
        fake_chat_session.user_id = test_user_id
        fake_chat_session.tenant_id = str(test_ws_id)

        def mock_exec(stmt):
            sql = str(stmt).lower()
            res = MagicMock()
            if "chat_session" in sql or "chatsession" in sql:
                res.scalar_one_or_none.return_value = fake_chat_session
            elif "workspacemember" in sql or "workspace_member" in sql:
                res.scalar_one_or_none.return_value = uuid.UUID(test_user_id)
            elif "document" in sql:
                fake_doc = MagicMock()
                res.scalar_one_or_none.return_value = fake_doc
            else:
                res.scalar_one_or_none.return_value = None
            return res

        mock_db_session.execute.side_effect = mock_exec

        class SessionContext:
            async def __aenter__(self):
                return mock_db_session
            async def __aexit__(self, *args):
                pass

        session_factory_mock = MagicMock(return_value=SessionContext())

        with patch("backend.modules.chat.services.chat_orchestrator.get_redis_client", return_value=None), \
             patch("backend.modules.chat.services.chat_orchestrator.get_session_factory", return_value=session_factory_mock), \
             patch("backend.modules.chat.services.chat_orchestrator.ChatRepository") as mock_repo_cls, \
             patch("backend.modules.analytics.services.quota.QuotaGovernor.record_token_usage", new_callable=AsyncMock) as mock_record_quota:
            mock_repo_inst = MagicMock()
            mock_repo_inst.list_messages = AsyncMock(return_value=[])
            mock_repo_inst.add_message = AsyncMock()
            mock_repo_cls.return_value = mock_repo_inst

            async for _ in orchestrator.stream_chat(
                session_id=test_session_id,
                tenant_id=test_tenant_id,
                user_id=test_user_id,
                query="What is Veritas-RAG?",
                correlation_id="cor-token-provider"
            ):
                pass

            assert mock_record_quota.called
            call_kwargs = mock_record_quota.call_args[1]
            assert call_kwargs["prompt_tokens"] == 55
            assert call_kwargs["completion_tokens"] == 120

    @pytest.mark.asyncio
    async def test_chat_004_fallback_token_usage_heuristic(self):
        """CHAT-004: Fallback heuristic is used when provider usage is absent."""
        test_tenant_id = str(uuid.uuid4())
        test_user_id = str(uuid.uuid4())
        test_session_id = str(uuid.uuid4())
        test_ws_id = uuid.uuid4()

        mock_wrapper = MagicMock()
        async def fake_stream_req(req, user_id=None, correlation_id=None):
            yield StreamingGenerationChunkDTO(
                chunk_index=0,
                text_delta="Four words answer text.",
                is_final=True,
                correlation_id=correlation_id,
                wrapper_metadata={"reliability_score": 0.90} # No usage dict
            )
        mock_wrapper.stream_request = fake_stream_req

        orchestrator = ChatOrchestrator(
            ai_wrapper_service=mock_wrapper,
            chat_repo=MagicMock()
        )

        mock_db_session = AsyncMock()
        fake_chat_session = MagicMock()
        fake_chat_session.user_id = test_user_id
        fake_chat_session.tenant_id = str(test_ws_id)

        def mock_exec(stmt):
            sql = str(stmt).lower()
            res = MagicMock()
            if "chat_session" in sql or "chatsession" in sql:
                res.scalar_one_or_none.return_value = fake_chat_session
            elif "workspacemember" in sql or "workspace_member" in sql:
                res.scalar_one_or_none.return_value = uuid.UUID(test_user_id)
            elif "document" in sql:
                fake_doc = MagicMock()
                res.scalar_one_or_none.return_value = fake_doc
            else:
                res.scalar_one_or_none.return_value = None
            return res

        mock_db_session.execute.side_effect = mock_exec

        class SessionContext:
            async def __aenter__(self):
                return mock_db_session
            async def __aexit__(self, *args):
                pass

        session_factory_mock = MagicMock(return_value=SessionContext())

        with patch("backend.modules.chat.services.chat_orchestrator.get_redis_client", return_value=None), \
             patch("backend.modules.chat.services.chat_orchestrator.get_session_factory", return_value=session_factory_mock), \
             patch("backend.modules.chat.services.chat_orchestrator.ChatRepository") as mock_repo_cls, \
             patch("backend.modules.analytics.services.quota.QuotaGovernor.record_token_usage", new_callable=AsyncMock) as mock_record_quota:
            mock_repo_inst = MagicMock()
            mock_repo_inst.list_messages = AsyncMock(return_value=[])
            mock_repo_inst.add_message = AsyncMock()
            mock_repo_cls.return_value = mock_repo_inst

            async for _ in orchestrator.stream_chat(
                session_id=test_session_id,
                tenant_id=test_tenant_id,
                user_id=test_user_id,
                query="Two words",
                correlation_id="cor-token-heuristic"
            ):
                pass

            assert mock_record_quota.called
            call_kwargs = mock_record_quota.call_args[1]
            # Two words * 2 = 4 prompt tokens; Four words * 2 = 8 completion tokens
            assert call_kwargs["prompt_tokens"] == 4
            assert call_kwargs["completion_tokens"] == 8

    @pytest.mark.asyncio
    async def test_chat_004_persistence_timeout_handled_gracefully(self):
        """CHAT-004: Persistence timeout does not crash stream generator."""
        test_tenant_id = str(uuid.uuid4())
        test_user_id = str(uuid.uuid4())
        test_session_id = str(uuid.uuid4())
        test_ws_id = uuid.uuid4()

        mock_wrapper = MagicMock()
        async def fake_stream_req(req, user_id=None, correlation_id=None):
            yield StreamingGenerationChunkDTO(
                chunk_index=0,
                text_delta="Answer text",
                is_final=True,
                correlation_id=correlation_id,
                wrapper_metadata={"reliability_score": 0.85}
            )
        mock_wrapper.stream_request = fake_stream_req

        orchestrator = ChatOrchestrator(
            ai_wrapper_service=mock_wrapper,
            chat_repo=MagicMock()
        )

        mock_db_session = AsyncMock()
        fake_chat_session = MagicMock()
        fake_chat_session.user_id = test_user_id
        fake_chat_session.tenant_id = str(test_ws_id)

        def mock_exec(stmt):
            sql = str(stmt).lower()
            res = MagicMock()
            if "chat_session" in sql or "chatsession" in sql:
                res.scalar_one_or_none.return_value = fake_chat_session
            elif "workspacemember" in sql or "workspace_member" in sql:
                res.scalar_one_or_none.return_value = uuid.UUID(test_user_id)
            elif "document" in sql:
                fake_doc = MagicMock()
                res.scalar_one_or_none.return_value = fake_doc
            else:
                res.scalar_one_or_none.return_value = None
            return res

        mock_db_session.execute.side_effect = mock_exec

        class SessionContext:
            async def __aenter__(self):
                return mock_db_session
            async def __aexit__(self, *args):
                pass

        session_factory_mock = MagicMock(return_value=SessionContext())

        with patch("backend.modules.chat.services.chat_orchestrator.get_redis_client", return_value=None), \
             patch("backend.modules.chat.services.chat_orchestrator.get_session_factory", return_value=session_factory_mock), \
             patch("backend.modules.chat.services.chat_orchestrator.ChatRepository") as mock_repo_cls, \
             patch("asyncio.wait_for", side_effect=asyncio.TimeoutError("Persistence timeout")):
            mock_repo_inst = MagicMock()
            mock_repo_inst.list_messages = AsyncMock(return_value=[])
            mock_repo_inst.add_message = AsyncMock()
            mock_repo_cls.return_value = mock_repo_inst

            emitted = []
            async for sse_line in orchestrator.stream_chat(
                session_id=test_session_id,
                tenant_id=test_tenant_id,
                user_id=test_user_id,
                query="Test query",
                correlation_id="cor-timeout"
            ):
                emitted.append(sse_line)

            # Stream finished cleanly and emitted terminal done event despite persistence timeout
            full_output = "".join(emitted)
            assert "event: done" in full_output


# ==============================================================================
# CHAT-005: Orchestrator Mid-Stream Exception Handling & Quota Protection
# ==============================================================================
class TestChat005MidStreamExceptionHandling:
    """CHAT-005: Mid-stream exceptions emit SSE error and strictly prevent assistant persistence and quota charge."""

    @pytest.mark.asyncio
    async def test_chat_005_orchestrator_midstream_exception_emits_error_and_skips_persistence(self):
        from backend.core.exceptions import LLMProviderException

        test_tenant_id = str(uuid.uuid4())
        test_user_id = str(uuid.uuid4())
        test_session_id = str(uuid.uuid4())
        test_ws_id = uuid.uuid4()

        mock_wrapper = MagicMock()
        async def failing_stream_req(req, user_id=None, correlation_id=None):
            yield StreamingGenerationChunkDTO(
                chunk_index=0,
                text_delta="Partial text before crash...",
                is_final=False,
                correlation_id=correlation_id
            )
            # Simulate provider aborting mid-stream
            raise LLMProviderException(message="LLM provider rate limit exceeded", provider_name="openrouter")

        mock_wrapper.stream_request = failing_stream_req

        orchestrator = ChatOrchestrator(
            ai_wrapper_service=mock_wrapper,
            chat_repo=MagicMock()
        )

        mock_db_session = AsyncMock()
        fake_chat_session = MagicMock()
        fake_chat_session.user_id = test_user_id
        fake_chat_session.tenant_id = str(test_ws_id)

        def mock_exec(stmt):
            sql = str(stmt).lower()
            res = MagicMock()
            if "chat_session" in sql or "chatsession" in sql:
                res.scalar_one_or_none.return_value = fake_chat_session
            elif "workspacemember" in sql or "workspace_member" in sql:
                res.scalar_one_or_none.return_value = uuid.UUID(test_user_id)
            elif "document" in sql:
                fake_doc = MagicMock()
                res.scalar_one_or_none.return_value = fake_doc
            else:
                res.scalar_one_or_none.return_value = None
            return res

        mock_db_session.execute.side_effect = mock_exec

        class SessionContext:
            async def __aenter__(self):
                return mock_db_session
            async def __aexit__(self, *args):
                pass

        session_factory_mock = MagicMock(return_value=SessionContext())

        with patch("backend.modules.chat.services.chat_orchestrator.get_redis_client", return_value=None), \
             patch("backend.modules.chat.services.chat_orchestrator.get_session_factory", return_value=session_factory_mock), \
             patch("backend.modules.chat.services.chat_orchestrator.ChatRepository") as mock_repo_cls, \
             patch("backend.modules.analytics.services.quota.QuotaGovernor.record_token_usage", new_callable=AsyncMock) as mock_record_quota:
            mock_repo_inst = MagicMock()
            mock_repo_inst.list_messages = AsyncMock(return_value=[])
            mock_repo_inst.add_message = AsyncMock()
            mock_repo_cls.return_value = mock_repo_inst

            emitted = []
            async for sse_line in orchestrator.stream_chat(
                session_id=test_session_id,
                tenant_id=test_tenant_id,
                user_id=test_user_id,
                query="Query before crash",
                correlation_id="cor-crash-midstream"
            ):
                emitted.append(sse_line)

            full_output = "".join(emitted)
            # Emitted canonical error event
            assert "event: error" in full_output
            assert "INTERNAL_ERROR" in full_output

            # Crucial assertion: Assistant message was NOT persisted
            # add_message was called only ONCE for initial user message, NEVER for assistant
            assistant_saves = [
                call for call in mock_repo_inst.add_message.call_args_list
                if call[1].get("dto") and call[1]["dto"].role == "assistant"
            ]
            assert len(assistant_saves) == 0, "Assistant message must not be persisted on terminal error"

            # Quota usage was NOT charged on terminal error
            assert not mock_record_quota.called, "Quota usage must not be recorded on terminal error"


# ==============================================================================
# OBS-002: TTFT Metric Single Observation Check
# ==============================================================================
class TestOBS002TTFTSingleObservation:
    """OBS-002: Ensure TTFT histogram is observed exactly once per applicable request."""

    @pytest.mark.asyncio
    async def test_obs_002_streaming_ttft_single_observation(self):
        """OBS-002: Streaming generation does not observe SSE_TTFT_SECONDS twice."""
        test_tenant_id = str(uuid.uuid4())
        test_user_id = str(uuid.uuid4())
        test_session_id = str(uuid.uuid4())
        test_ws_id = uuid.uuid4()

        mock_wrapper = MagicMock()
        async def fake_stream_req(req, user_id=None, correlation_id=None):
            yield StreamingGenerationChunkDTO(
                chunk_index=0,
                text_delta="Token 1 ",
                is_final=False,
                correlation_id=correlation_id
            )
            yield StreamingGenerationChunkDTO(
                chunk_index=1,
                text_delta="Token 2 ",
                is_final=True,
                correlation_id=correlation_id,
                wrapper_metadata={"reliability_score": 0.90}
            )
        mock_wrapper.stream_request = fake_stream_req

        orchestrator = ChatOrchestrator(
            ai_wrapper_service=mock_wrapper,
            chat_repo=MagicMock()
        )

        mock_db_session = AsyncMock()
        fake_chat_session = MagicMock()
        fake_chat_session.user_id = test_user_id
        fake_chat_session.tenant_id = str(test_ws_id)

        def mock_exec(stmt):
            sql = str(stmt).lower()
            res = MagicMock()
            if "chat_session" in sql or "chatsession" in sql:
                res.scalar_one_or_none.return_value = fake_chat_session
            elif "workspacemember" in sql or "workspace_member" in sql:
                res.scalar_one_or_none.return_value = uuid.UUID(test_user_id)
            elif "document" in sql:
                fake_doc = MagicMock()
                res.scalar_one_or_none.return_value = fake_doc
            else:
                res.scalar_one_or_none.return_value = None
            return res

        mock_db_session.execute.side_effect = mock_exec

        class SessionContext:
            async def __aenter__(self):
                return mock_db_session
            async def __aexit__(self, *args):
                pass

        session_factory_mock = MagicMock(return_value=SessionContext())

        with patch("backend.modules.chat.services.chat_orchestrator.get_redis_client", return_value=None), \
             patch("backend.modules.chat.services.chat_orchestrator.get_session_factory", return_value=session_factory_mock), \
             patch("backend.modules.chat.services.chat_orchestrator.ChatRepository") as mock_repo_cls, \
             patch("backend.observability.metrics.prometheus.SSE_TTFT_SECONDS.observe") as mock_ttft_observe:
            mock_repo_inst = MagicMock()
            mock_repo_inst.list_messages = AsyncMock(return_value=[])
            mock_repo_inst.add_message = AsyncMock()
            mock_repo_cls.return_value = mock_repo_inst

            async for _ in orchestrator.stream_chat(
                session_id=test_session_id,
                tenant_id=test_tenant_id,
                user_id=test_user_id,
                query="Test query",
                correlation_id="cor-ttft-single"
            ):
                pass

            # Assert observed exactly once on first token, not on second token or duplicate
            assert mock_ttft_observe.call_count == 1
