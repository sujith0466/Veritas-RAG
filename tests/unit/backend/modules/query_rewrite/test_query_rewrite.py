import pytest
from backend.modules.query_rewrite.schemas.rewrite_dto import RewriteRequestDTO
from backend.modules.query_rewrite.strategies.decomposition import DecompositionRewriter
from backend.modules.query_rewrite.strategies.hyde import HyDERewriter
from backend.modules.query_rewrite.strategies.disambiguation import DisambiguationRewriter
from backend.modules.query_rewrite.services.clarification_engine import ClarificationEngine


@pytest.fixture
def clarification_engine():
    decomp = DecompositionRewriter()
    hyde = HyDERewriter()
    disambig = DisambiguationRewriter()
    return ClarificationEngine(decomp, hyde, disambig)


def test_clarification_engine_ambiguous(clarification_engine):
    request = RewriteRequestDTO(original_query="What is the architecture of apple?")
    result = clarification_engine.rewrite_query(request)
    
    assert result["status"] == "CLARIFICATION_REQUIRED"
    assert "Apple Inc." in result["clarification"].options[0]


def test_clarification_engine_decomposition(clarification_engine):
    request = RewriteRequestDTO(original_query="What is FastAPI and how does it compare to Django?")
    result = clarification_engine.rewrite_query(request)
    
    assert result["status"] == "REWRITTEN"
    assert result["decomposed"].is_complex is True
    assert len(result["decomposed"].sub_queries) > 1
    assert "hypothetical" in result["hyde"].hypothetical_document


def test_clarification_engine_simple(clarification_engine):
    request = RewriteRequestDTO(original_query="How does vector search work?")
    result = clarification_engine.rewrite_query(request)
    
    assert result["status"] == "REWRITTEN"
    assert result["decomposed"].is_complex is False
    assert len(result["decomposed"].sub_queries) == 1
