import re
from backend.modules.reliability.schemas.reliability_dto import ReliableCandidateDTO
from backend.modules.confidence.schemas.confidence_dto import CoverageMetricsDTO


class CoverageAnalyzer:
    """Analyzes the semantic coverage of retrieved evidence against the query."""
    
    def __init__(self):
        # Very simple delimiters for clause splitting (heuristic)
        self.clause_delimiters = re.compile(r'\b(?:and|or|but|because|if|then|when|where)\b|[.,;?!]')
        
    def _extract_clauses(self, query: str) -> list[str]:
        """Extract logical clauses from the query string."""
        raw_clauses = self.clause_delimiters.split(query.lower())
        clauses = [c.strip() for c in raw_clauses if len(c.strip()) > 3]
        if not clauses:
            return [query.lower().strip()]
        return clauses

    def _tokenize(self, text: str) -> set[str]:
        """Simple whitespace/punctuation tokenizer."""
        return set(re.findall(r'\b\w+\b', text.lower()))
        
    def analyze(self, query: str, candidates: list[ReliableCandidateDTO]) -> CoverageMetricsDTO:
        """Calculate coverage score by checking token overlap of query clauses in evidence."""
        if not candidates:
            return CoverageMetricsDTO(coverage_score=0.0, clauses_covered=0, total_clauses=1)
            
        clauses = self.extract_clauses(query)
        total_clauses = len(clauses)
        
        # Combine all candidate texts into one large token set for simple coverage check
        combined_text = " ".join([c.content for c in candidates])
        evidence_tokens = self._tokenize(combined_text)
        
        covered_clauses = 0
        for clause in clauses:
            clause_tokens = self._tokenize(clause)
            if not clause_tokens:
                continue
                
            # If > 50% of important tokens in a clause exist in evidence, we consider it covered
            # In a production NLI system, this would be a model call. This is the heuristic baseline.
            overlap = len(clause_tokens.intersection(evidence_tokens))
            if overlap / len(clause_tokens) >= 0.5:
                covered_clauses += 1
                
        coverage_score = covered_clauses / total_clauses if total_clauses > 0 else 0.0
        
        return CoverageMetricsDTO(
            coverage_score=coverage_score,
            clauses_covered=covered_clauses,
            total_clauses=total_clauses
        )
        
    def extract_clauses(self, query: str) -> list[str]:
        """Public alias for clause extraction."""
        return self._extract_clauses(query)
