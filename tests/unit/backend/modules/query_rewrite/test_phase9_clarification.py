"""Unit tests for Phase 9 Clarification Engine & State Manager."""

import time

import pytest

from backend.modules.query_rewrite.schemas.errors import ClarificationGenerationFailed
from backend.modules.query_rewrite.schemas.rewrite_dto import (
    ClarificationResumeRequestDTO,
    ClarificationStatus,
    RewriteRequestDTOv2,
)
from backend.modules.query_rewrite.services.clarification_engine import ClarificationEngine
from backend.modules.query_rewrite.services.clarification_state_manager import (
    ClarificationStateManager,
)
from backend.modules.query_rewrite.strategies.decomposition import DecompositionRewriter
from backend.modules.query_rewrite.strategies.disambiguation import DisambiguationRewriter
from backend.modules.query_rewrite.strategies.hyde import HyDERewriter


@pytest.fixture
def state_manager():
    return ClarificationStateManager(default_ttl_seconds=10)


@pytest.fixture
def clarification_engine(state_manager):
    return ClarificationEngine(
        decomposition=DecompositionRewriter(),
        hyde=HyDERewriter(),
        disambiguation=DisambiguationRewriter(),
        state_manager=state_manager,
    )


@pytest.mark.asyncio
async def test_evaluate_and_clarify_ambiguous_query(clarification_engine):
    req = RewriteRequestDTOv2(original_query="What is the architecture of apple?", tenant_id="t1")
    clarif = await clarification_engine.evaluate_and_clarify(req, correlation_id="c_apple")
    assert clarif is not None
    assert "Apple Inc." in clarif.options[0] or "Fruit" in clarif.options[1]

    state = clarification_engine.get_state("c_apple")
    assert state is not None
    assert state.status == ClarificationStatus.REQUIRED
    assert state.original_query == "What is the architecture of apple?"


@pytest.mark.asyncio
async def test_evaluate_and_clarify_low_coverage(clarification_engine):
    req = RewriteRequestDTOv2(
        original_query="How do I configure the internal routing mechanism?",
        tenant_id="t1",
        coverage_score=0.15,
    )
    clarif = await clarification_engine.evaluate_and_clarify(req, correlation_id="c_low_cov")
    assert clarif is not None
    assert "low retrieval coverage" in clarif.question_text


@pytest.mark.asyncio
async def test_resume_clarification_success(clarification_engine):
    # Setup initial state
    req = RewriteRequestDTOv2(original_query="What is the architecture of apple?", tenant_id="t1")
    await clarification_engine.evaluate_and_clarify(req, correlation_id="c_resume")

    resume_req = ClarificationResumeRequestDTO(
        correlation_id="c_resume",
        tenant_id="t1",
        selected_option="Apple Inc. (Technology)",
        additional_context="Focusing on iOS security",
    )
    resolved = await clarification_engine.resume_clarification(resume_req)
    assert resolved.correlation_id == "c_resume"
    assert "Apple Inc. (Technology)" in resolved.clarified_query
    assert "iOS security" in resolved.clarified_query

    state = clarification_engine.get_state("c_resume")
    assert state.status == ClarificationStatus.RESOLVED


def test_clarification_state_manager_expiration(state_manager):
    state_manager.default_ttl = 1  # 1 second TTL
    state_manager.save_state("c_exp", "t1", "query", "question?", ["A", "B"])
    assert state_manager.get_state("c_exp").status == ClarificationStatus.REQUIRED
    time.sleep(1.1)
    # Getting expired state should flip status to TIMEOUT
    expired_state = state_manager.get_state("c_exp")
    assert expired_state.status == ClarificationStatus.TIMEOUT

    # Attempting to resume expired state should raise error
    with pytest.raises(ClarificationGenerationFailed):
        state_manager.resolve_state(
            ClarificationResumeRequestDTO(correlation_id="c_exp", tenant_id="t1", selected_option="A")
        )
