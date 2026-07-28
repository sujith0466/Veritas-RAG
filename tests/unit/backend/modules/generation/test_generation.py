import pytest
from backend.modules.generation.schemas.generation_dto import GenerationRequestDTO
from backend.modules.generation.services.citation_extractor import CitationExtractor
from backend.modules.generation.services.generation_service import GroundedGenerationService


@pytest.fixture
def generation_service():
    extractor = CitationExtractor()
    return GroundedGenerationService(citation_extractor=extractor, llm_provider=None)


def test_grounded_generation_no_evidence(generation_service):
    request = GenerationRequestDTO(
        query="What is RAG?",
        evidence_chunks=[],
        correlation_id="corr_gen_1"
    )
    result = generation_service.generate(request)
    assert result.is_fully_grounded is False
    assert result.evidence_used_count == 0
    assert "Insufficient" in result.answer_text


def test_grounded_generation_with_evidence(generation_service):
    evidence = [
        {"chunk_id": "chk_1", "document_id": "doc_1", "content": "RAG stands for Retrieval-Augmented Generation.", "score": 0.95},
        {"chunk_id": "chk_2", "document_id": "doc_1", "content": "It combines retrieval with generation models.", "score": 0.88},
    ]
    request = GenerationRequestDTO(
        query="What is RAG?",
        evidence_chunks=evidence,
        correlation_id="corr_gen_2"
    )
    result = generation_service.generate(request)
    assert result.evidence_used_count == 2
    assert len(result.citations) > 0
    # All citations must trace to a real chunk
    for citation in result.citations:
        assert citation.chunk_id in ["chk_1", "chk_2"]


def test_citation_extractor_check_grounding():
    extractor = CitationExtractor()
    # A fully grounded answer has [N] in every sentence
    grounded_text = "RAG stands for retrieval augmented generation. [1] It uses a retrieval step before the LLM call. [2]"
    citations = extractor.extract(grounded_text, [
        {"chunk_id": "chk_1", "document_id": "doc_1", "content": "RAG stands for retrieval augmented generation.", "score": 0.9},
        {"chunk_id": "chk_2", "document_id": "doc_1", "content": "It uses a retrieval step before the LLM call.", "score": 0.8},
    ])
    assert extractor.check_grounding(grounded_text, citations) is True


def test_citation_extractor_flags_ungrounded():
    extractor = CitationExtractor()
    # One sentence lacks a citation marker
    ungrounded_text = "RAG is very useful. [1] However, it has many downsides that are not covered in evidence."
    citations = extractor.extract(ungrounded_text, [
        {"chunk_id": "chk_1", "document_id": "doc_1", "content": "RAG is very useful.", "score": 0.9},
    ])
    assert extractor.check_grounding(ungrounded_text, citations) is False


def test_evidence_aware_grounding_accepts_supported_citations():
    extractor = CitationExtractor()
    evidence = [
        {"chunk_id": "chk_1", "document_id": "doc_1", "content": "RAGuard reduces hallucinations and uses hybrid retrieval.", "score": 0.9},
    ]
    text = "RAGuard reduces hallucinations. [1] It uses hybrid retrieval. [1]"
    citations = extractor.extract(text, evidence)

    assert extractor.check_grounding(text, citations, evidence) is True


def test_evidence_aware_grounding_rejects_missing_citations():
    extractor = CitationExtractor()
    evidence = [
        {"chunk_id": "chk_1", "document_id": "doc_1", "content": "RAGuard reduces hallucinations.", "score": 0.9},
    ]
    text = "RAGuard reduces hallucinations. [1] It uses hybrid retrieval."
    citations = extractor.extract(text, evidence)

    assert extractor.check_grounding(text, citations, evidence) is False


def test_evidence_aware_grounding_rejects_empty_evidence():
    extractor = CitationExtractor()
    evidence = [
        {"chunk_id": "chk_1", "document_id": "doc_1", "content": "", "score": 0.9},
    ]
    text = "RAGuard reduces hallucinations. [1]"
    citations = extractor.extract(text, evidence)

    assert extractor.check_grounding(text, citations, evidence) is False


def test_evidence_aware_grounding_rejects_invalid_citation_index():
    extractor = CitationExtractor()
    evidence = [
        {"chunk_id": "chk_1", "document_id": "doc_1", "content": "RAGuard reduces hallucinations.", "score": 0.9},
    ]
    text = "RAGuard reduces hallucinations. [2]"
    citations = extractor.extract(text, evidence)

    assert extractor.check_grounding(text, citations, evidence) is False


def test_evidence_aware_grounding_rejects_unsupported_claims():
    extractor = CitationExtractor()
    evidence = [
        {"chunk_id": "chk_1", "document_id": "doc_1", "content": "RAGuard reduces hallucinations.", "score": 0.9},
    ]
    text = "RAGuard guarantees zero latency. [1]"
    citations = extractor.extract(text, evidence)

    assert extractor.check_grounding(text, citations, evidence) is False
