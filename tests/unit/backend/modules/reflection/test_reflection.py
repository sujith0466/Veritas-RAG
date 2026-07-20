import pytest
from backend.modules.generation.schemas.generation_dto import GroundedAnswerDTO, CitationDTO
from backend.modules.reflection.schemas.reflection_dto import ReflectionRequestDTO, ClaimVerdict
from backend.modules.reflection.services.claim_validator import ClaimValidator
from backend.modules.reflection.services.reflection_engine import ReflectionEngine


@pytest.fixture
def reflection_engine():
    validator = ClaimValidator()
    return ReflectionEngine(claim_validator=validator)


def _make_answer(answer_text: str, citations: list[CitationDTO]) -> GroundedAnswerDTO:
    return GroundedAnswerDTO(
        answer_text=answer_text,
        citations=citations,
        is_fully_grounded=True,
        correlation_id="corr_ref_1",
        evidence_used_count=len(citations)
    )


def test_reflection_fully_supported(reflection_engine):
    citations = [
        CitationDTO(
            citation_index=1,
            chunk_id="chk_1",
            document_id="doc_1",
            excerpt="RAG stands for Retrieval Augmented Generation and combines retrieval with LLMs.",
            relevance_score=0.95
        )
    ]
    answer = _make_answer(
        "RAG stands for Retrieval Augmented Generation and combines retrieval with LLMs. [1]",
        citations
    )
    request = ReflectionRequestDTO(grounded_answer=answer, correlation_id="corr_ref_1")
    result = reflection_engine.reflect(request)

    assert result.overall_verdict == ClaimVerdict.SUPPORTED
    assert result.hallucination_score == 0.0
    assert result.is_safe_to_serve is True


def test_reflection_detects_unsupported(reflection_engine):
    citations = [
        CitationDTO(
            citation_index=1,
            chunk_id="chk_1",
            document_id="doc_1",
            excerpt="Vector databases store embeddings for similarity search.",
            relevance_score=0.80
        )
    ]
    # The second sentence references [1] but talks about something not in the excerpt
    answer = _make_answer(
        "Vector databases store embeddings for similarity search. [1] "
        "Quantum entanglement drives the embedding compression algorithm exponentially. [1]",
        citations
    )
    request = ReflectionRequestDTO(grounded_answer=answer, correlation_id="corr_ref_2")
    result = reflection_engine.reflect(request)

    assert result.hallucination_score > 0
    # One supported, one unsupported → hallucination_score = 0.5
    assert result.overall_verdict in [ClaimVerdict.UNSUPPORTED, ClaimVerdict.CONTRADICTED]


def test_reflection_detects_numeric_contradiction(reflection_engine):
    citations = [
        CitationDTO(
            citation_index=1,
            chunk_id="chk_1",
            document_id="doc_1",
            excerpt="Revenue was 5 million dollars in 2023.",
            relevance_score=0.90
        )
    ]
    # Claim states 10 million — contradicts the excerpt's 5 million
    answer = _make_answer(
        "Revenue was 10 million dollars in 2023. [1]",
        citations
    )
    request = ReflectionRequestDTO(grounded_answer=answer, correlation_id="corr_ref_3")
    result = reflection_engine.reflect(request)

    assert result.overall_verdict == ClaimVerdict.CONTRADICTED
    assert result.is_safe_to_serve is False


def test_claim_validator_supported():
    validator = ClaimValidator()
    citations = [
        CitationDTO(
            citation_index=1,
            chunk_id="c1", document_id="d1",
            excerpt="FastAPI is an async Python web framework built on Starlette.",
            relevance_score=1.0
        )
    ]
    result = validator.validate_claim(
        "FastAPI is an async Python framework built on Starlette.",
        citation_index=1,
        citations=citations
    )
    assert result.verdict == ClaimVerdict.SUPPORTED
