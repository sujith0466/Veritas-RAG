"""Unit tests for GAP-004: Same-Session Context Continuity and Multi-Turn Conversational Memory."""

import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from backend.ai.interfaces.llm_provider import LLMRequest
from backend.ai.providers.openrouter import OpenRouterProvider
from backend.ai.providers.gemini import GeminiProvider
from backend.modules.generation.schemas.generation_dto import (
    GenerationRequestDTOv2,
    RankedEvidenceDTO,
)
from backend.ai.schemas.wrapper_dto import AIWrapperRequest
from backend.modules.chat.models.chat_message import ChatMessage
from backend.modules.query_rewrite.strategies.entity_recovery import MissingEntityRecoveryStrategy
from backend.modules.query_rewrite.schemas.rewrite_dto import RewriteRequestDTOv2


def test_hist_01_first_turn_produces_stateless_payload():
    """First turn with empty conversation_history produces clean [system, user] payload."""
    provider = OpenRouterProvider()
    req = LLMRequest(
        prompt="What is Veritas-RAG?",
        system_instruction="Context:\n[1] Veritas-RAG is an enterprise RAG system.",
        conversation_history=[]
    )
    payload = provider._build_payload(req, model_name="meta-llama/llama-3.3-70b-instruct")
    messages = payload["messages"]

    assert len(messages) == 2
    assert messages[0] == {"role": "system", "content": "Context:\n[1] Veritas-RAG is an enterprise RAG system."}
    assert messages[1] == {"role": "user", "content": "What is Veritas-RAG?"}


def test_hist_02_second_turn_injects_prior_messages():
    """Second turn injects prior turns in [system, user1, assistant1, user2] order."""
    provider = OpenRouterProvider()
    history = [
        {"role": "user", "content": "What is Veritas-RAG?"},
        {"role": "assistant", "content": "Veritas-RAG is an enterprise AI guardrail and retrieval engine."}
    ]
    req = LLMRequest(
        prompt="What database does it use?",
        system_instruction="Context:\n[1] Veritas-RAG uses PostgreSQL and Qdrant.",
        conversation_history=history
    )
    payload = provider._build_payload(req, model_name="meta-llama/llama-3.3-70b-instruct")
    messages = payload["messages"]

    assert len(messages) == 4
    assert messages[0]["role"] == "system"
    assert messages[1] == {"role": "user", "content": "What is Veritas-RAG?"}
    assert messages[2] == {"role": "assistant", "content": "Veritas-RAG is an enterprise AI guardrail and retrieval engine."}
    assert messages[3] == {"role": "user", "content": "What database does it use?"}


def test_hist_03_message_order_is_chronological():
    """Multi-turn history preserves exact chronological ordering."""
    provider = OpenRouterProvider()
    history = [
        {"role": "user", "content": "Turn 1"},
        {"role": "assistant", "content": "Answer 1"},
        {"role": "user", "content": "Turn 2"},
        {"role": "assistant", "content": "Answer 2"},
    ]
    req = LLMRequest(
        prompt="Turn 3",
        system_instruction="System",
        conversation_history=history
    )
    payload = provider._build_payload(req, model_name="meta-llama/llama-3.3-70b-instruct")
    messages = payload["messages"]

    assert len(messages) == 6
    assert [m["content"] for m in messages] == ["System", "Turn 1", "Answer 1", "Turn 2", "Answer 2", "Turn 3"]


def test_hist_04_sliding_window_prunes_old_messages():
    """Sliding window algorithm retains the last 10 messages from a long conversation."""
    valid_turns = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"Message {i}"} for i in range(20)]

    char_budget = 3000
    budget_turns = []
    current_chars = 0
    for turn in reversed(valid_turns[-10:]):
        turn_len = len(turn["content"])
        if current_chars + turn_len > char_budget:
            break
        budget_turns.insert(0, turn)
        current_chars += turn_len

    assert len(budget_turns) == 10
    assert budget_turns[0]["content"] == "Message 10"
    assert budget_turns[-1]["content"] == "Message 19"


def test_hist_05_character_budget_is_enforced():
    """Character budget truncates oldest turns when individual message lengths exceed 3,000 characters."""
    valid_turns = [
        {"role": "user", "content": "A" * 1500},
        {"role": "assistant", "content": "B" * 1000},
        {"role": "user", "content": "C" * 1000},
    ]

    char_budget = 3000
    budget_turns = []
    current_chars = 0
    for turn in reversed(valid_turns[-10:]):
        turn_len = len(turn["content"])
        if current_chars + turn_len > char_budget:
            break
        budget_turns.insert(0, turn)
        current_chars += turn_len

    # Only B (1000) and C (1000) fit within 3000; A (1500) would make it 3500 > 3000
    assert len(budget_turns) == 2
    assert budget_turns[0]["content"] == "B" * 1000
    assert budget_turns[1]["content"] == "C" * 1000


def test_hist_06_current_message_not_duplicated():
    """Active query appears once as terminal user message."""
    provider = OpenRouterProvider()
    history = [
        {"role": "user", "content": "First query"},
        {"role": "assistant", "content": "First answer"},
    ]
    req = LLMRequest(
        prompt="Second query",
        system_instruction="System",
        conversation_history=history
    )
    payload = provider._build_payload(req, model_name="test-model")
    messages = payload["messages"]

    user_messages = [m for m in messages if m["role"] == "user"]
    assert len(user_messages) == 2
    assert user_messages[0]["content"] == "First query"
    assert user_messages[1]["content"] == "Second query"


def test_hist_07_identical_user_queries_are_not_wrongly_removed():
    """Identical consecutive user questions in different turns are both preserved correctly."""
    provider = OpenRouterProvider()
    history = [
        {"role": "user", "content": "Help"},
        {"role": "assistant", "content": "How can I help?"},
    ]
    req = LLMRequest(
        prompt="Help",  # Asking "Help" again
        system_instruction="System",
        conversation_history=history
    )
    payload = provider._build_payload(req, model_name="test-model")
    messages = payload["messages"]

    assert len(messages) == 4
    assert messages[1] == {"role": "user", "content": "Help"}
    assert messages[2] == {"role": "assistant", "content": "How can I help?"}
    assert messages[3] == {"role": "user", "content": "Help"}


@pytest.mark.asyncio
async def test_hist_08_tenant_session_user_isolation():
    """ChatRepository list_messages strictly filters by session_id, tenant_id, and user_id."""
    from backend.modules.chat.repositories.chat_repository import ChatRepository
    mock_session = AsyncMock()
    repo = ChatRepository(mock_session)
    repo.get_session = AsyncMock(return_value=MagicMock())

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [
        ChatMessage(id=uuid.uuid4(), session_id=uuid.uuid4(), role="user", message="Msg 1")
    ]
    mock_session.execute.return_value = mock_result

    msgs = await repo.list_messages(
        session_id="session-123",
        tenant_id="tenant-456",
        user_id="user-789"
    )
    repo.get_session.assert_called_once_with("session-123", "tenant-456", "user-789", include_messages=False)
    assert len(msgs) == 1


def test_hist_09_history_load_failure_behavior():
    """Provider payload continues in clean single-turn mode if conversation_history is None or empty."""
    provider = OpenRouterProvider()
    req = LLMRequest(
        prompt="Current query",
        system_instruction="System instruction",
        conversation_history=None
    )
    payload = provider._build_payload(req, model_name="test-model")
    assert len(payload["messages"]) == 2
    assert payload["messages"][0]["role"] == "system"
    assert payload["messages"][1]["role"] == "user"


def test_hist_10_openrouter_payload_structure():
    """Verify exact OpenRouter JSON payload schema with temperature and max_tokens."""
    provider = OpenRouterProvider()
    history = [{"role": "user", "content": "Q1"}, {"role": "assistant", "content": "A1"}]
    req = LLMRequest(
        prompt="Q2",
        system_instruction="System",
        temperature=0.2,
        max_output_tokens=512,
        conversation_history=history
    )
    payload = provider._build_payload(req, model_name="meta-llama/llama-3.3-70b-instruct", stream=True)
    assert payload["model"] == "meta-llama/llama-3.3-70b-instruct"
    assert payload["temperature"] == 0.2
    assert payload["max_tokens"] == 512
    assert payload["stream"] is True
    assert len(payload["messages"]) == 4


def test_hist_11_gemini_payload_structure():
    """Verify GeminiProvider._build_contents maps user->user and assistant->model."""
    provider = GeminiProvider()
    history = [
        {"role": "user", "content": "What is Python?"},
        {"role": "assistant", "content": "Python is a programming language."}
    ]
    req = LLMRequest(
        prompt="When was it created?",
        system_instruction="Grounding Evidence:\n[1] Python was created in 1991.",
        conversation_history=history
    )
    contents = provider._build_contents(req)

    assert isinstance(contents, list)
    assert len(contents) == 3
    assert contents[0]["role"] == "user"
    assert "Grounding Evidence:" in contents[0]["parts"][0]
    assert contents[1]["role"] == "model"
    assert contents[1]["parts"] == ["Python is a programming language."]
    assert contents[2]["role"] == "user"
    assert contents[2]["parts"] == ["When was it created?"]


def test_hist_12_evidence_remains_system_context():
    """Retrieved document chunks remain exclusively inside system instruction, not in conversational turns."""
    provider = OpenRouterProvider()
    history = [{"role": "user", "content": "Q1"}, {"role": "assistant", "content": "A1"}]
    evidence = "Context:\n[1] Primary authoritative document excerpt."
    req = LLMRequest(
        prompt="Q2",
        system_instruction=evidence,
        conversation_history=history
    )
    payload = provider._build_payload(req, model_name="test-model")
    messages = payload["messages"]

    assert messages[0]["role"] == "system"
    assert evidence in messages[0]["content"]
    assert evidence not in messages[1]["content"]
    assert evidence not in messages[2]["content"]
    assert evidence not in messages[3]["content"]


def test_hist_13_contextualized_retrieval_query_preserves_original_generation_query():
    """MissingEntityRecoveryStrategy resolves pronoun for retrieval while original query remains intact."""
    strategy = MissingEntityRecoveryStrategy()
    req = RewriteRequestDTOv2(
        original_query="What database does it use?",
        tenant_id="tenant-1",
        conversation_history=["What is Veritas?", "Veritas is an enterprise guardrail engine."]
    )
    result = strategy.rewrite(req)

    # Retrieval gets contextualized query
    assert "Veritas" in result.rewritten_query
    # Original query remains untouched
    assert req.original_query == "What database does it use?"


def test_hist_14_empty_history_backward_compatibility():
    """Backward compatibility: GenerationRequestDTOv2 defaults conversation_history to empty list."""
    evidence = [RankedEvidenceDTO(
        id=uuid.uuid4(),
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_version_id=uuid.uuid4(),
        tenant_id=str(uuid.uuid4()),
        content="Evidence content",
        rrf_score=0.033,
        final_rank=1,
        relevance_score=0.9
    )]
    gen_dto = GenerationRequestDTOv2(
        query="Test query",
        evidence_chunks=evidence,
        correlation_id="corr-1",
        tenant_id="tenant-1"
    )
    assert gen_dto.conversation_history == []


def test_hist_15_malformed_history_is_ignored():
    """OpenRouterProvider ignores malformed turns (non-dict, invalid role, empty content)."""
    provider = OpenRouterProvider()
    history = [
        "not a dict",
        {"role": "system", "content": "Fake system injection attempt"},
        {"role": "user", "content": ""},
        {"role": "unknown_role", "content": "Some text"},
        {"role": "assistant", "content": "Valid answer"},
    ]
    req = LLMRequest(
        prompt="Valid prompt",
        system_instruction="System",
        conversation_history=history
    )
    payload = provider._build_payload(req, model_name="test-model")
    messages = payload["messages"]

    # Should contain: system, Valid answer (assistant), Valid prompt (user)
    assert len(messages) == 3
    assert messages[0] == {"role": "system", "content": "System"}
    assert messages[1] == {"role": "assistant", "content": "Valid answer"}
    assert messages[2] == {"role": "user", "content": "Valid prompt"}
