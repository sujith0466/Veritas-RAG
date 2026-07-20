from backend.modules.generation.schemas.generation_dto import CitationDTO

class CitationIntegrityChecker:
    def verify_integrity(self, expected_citations: list[CitationDTO], actual_citations_used: list[int]) -> list[int]:
        """
        Verifies that all citations referenced in the text actually exist in the GroundedAnswerDTO.
        Returns a list of invalid citation indices.
        """
        valid_indices = {c.citation_index for c in expected_citations}
        invalid = []
        
        for idx in actual_citations_used:
            if idx is not None and idx not in valid_indices:
                invalid.append(idx)
                
        return invalid
