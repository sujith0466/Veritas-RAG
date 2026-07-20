import pytest
from backend.modules.validation.services.citation_checker import CitationIntegrityChecker
from backend.modules.generation.schemas.generation_dto import CitationDTO

def test_citation_integrity():
    checker = CitationIntegrityChecker()
    citations = [
        CitationDTO(citation_index=1, excerpt="ex1", chunk_id="c1", document_id="d1"),
        CitationDTO(citation_index=3, excerpt="ex3", chunk_id="c3", document_id="d3")
    ]
    
    invalid = checker.verify_integrity(citations, [1, 2, 3])
    assert invalid == [2]
