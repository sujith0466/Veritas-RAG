"""Unit tests for Phase 8 Query Rewrite strategies and orchestration."""

import pytest
from backend.modules.query_rewrite.schemas.rewrite_dto import (
    RewriteRequestDTOv2,
    RewriteStrategy,
)
from backend.modules.query_rewrite.strategies.hyde import HyDEStrategy
from backend.modules.query_rewrite.strategies.expansion import QueryExpansionStrategy
from backend.modules.query_rewrite.strategies.decomposition import QueryDecompositionStrategy
from backend.modules.query_rewrite.strategies.entity_recovery import MissingEntityRecoveryStrategy
from backend.modules.query_rewrite.services.strategy_selector import StrategySelector
from backend.modules.query_rewrite.services.rewrite_orchestrator import RewriteOrchestrator


def test_hyde_strategy_fallback():
    strategy = HyDEStrategy()
    request = RewriteRequestDTOv2(original_query="What is vector search?", tenant_id="t1")
    result = strategy.rewrite(request)
    assert result.strategy == RewriteStrategy.HYDE
    assert "hypothetical document" in result.rationale.lower()
    assert result.hypothetical_document is not None
    assert "Vector search" in result.rewritten_query or "vector search" in result.rewritten_query


def test_expansion_strategy():
    strategy = QueryExpansionStrategy()
    request = RewriteRequestDTOv2(original_query="increase revenue of ML contract", tenant_id="t1")
    result = strategy.rewrite(request)
    assert result.strategy == RewriteStrategy.EXPANSION
    assert "Machine Learning" in result.rewritten_query
    assert "rise" in result.rewritten_query or "grow" in result.rewritten_query
    assert len(result.expanded_terms) > 0


def test_decomposition_strategy_complex():
    strategy = QueryDecompositionStrategy()
    request = RewriteRequestDTOv2(
        original_query="What is FastAPI and what are its performance differences compared to Django?",
        tenant_id="t1",
    )
    result = strategy.rewrite(request)
    assert result.strategy == RewriteStrategy.DECOMPOSITION
    assert len(result.sub_queries) >= 2


def test_entity_recovery_strategy_with_history():
    strategy = MissingEntityRecoveryStrategy()
    request = RewriteRequestDTOv2(
        original_query="Did they approve it?",
        tenant_id="t1",
        conversation_history=[
            "We submitted the Service Level Agreement to the executive committee.",
            "The executive committee reviewed all terms."
        ]
    )
    result = strategy.rewrite(request)
    assert result.strategy == RewriteStrategy.ENTITY_RECOVERY
    # Pronouns should be detected and resolved from noun phrases or marked
    assert len(result.resolved_entities) > 0


def test_strategy_selector_routing():
    strategies = {
        RewriteStrategy.HYDE: HyDEStrategy(),
        RewriteStrategy.EXPANSION: QueryExpansionStrategy(),
        RewriteStrategy.DECOMPOSITION: QueryDecompositionStrategy(),
        RewriteStrategy.ENTITY_RECOVERY: MissingEntityRecoveryStrategy(),
    }
    selector = StrategySelector(strategies)

    # Hint override
    req_hint = RewriteRequestDTOv2(original_query="test", tenant_id="t1", strategy_hint=RewriteStrategy.EXPANSION)
    assert selector.select(req_hint).get_strategy_name() == RewriteStrategy.EXPANSION

    # Decomposition signal
    req_decomp = RewriteRequestDTOv2(original_query="Compare X and Y", tenant_id="t1")
    assert selector.select(req_decomp).get_strategy_name() == RewriteStrategy.DECOMPOSITION


def test_rewrite_orchestrator_history():
    orchestrator = RewriteOrchestrator()
    req = RewriteRequestDTOv2(original_query="How to increase customer retention?", tenant_id="t1")
    res = orchestrator.rewrite(req)
    assert res.original_query == "How to increase customer retention?"
    history = orchestrator.get_history()
    assert len(history) == 1
    assert history[0].original_query == res.original_query
