import re
from itertools import combinations
from backend.modules.reliability.schemas.reliability_dto import ReliableCandidateDTO
from backend.modules.confidence.schemas.confidence_dto import ContradictionReportDTO


class ContradictionDetector:
    """Detects potential contradictions among retrieved evidence chunks."""
    
    def __init__(self):
        # Basic heuristic patterns for contradiction detection (e.g., numbers, dates)
        self.numeric_pattern = re.compile(r'\b\d+(?:[,.]\d+)?(?:k|m|b|%| dollars)?\b', re.IGNORECASE)
        self.date_pattern = re.compile(r'\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]* \d{1,2},? \d{4}\b', re.IGNORECASE)

    def _extract_entities(self, text: str) -> set[str]:
        """Extract numeric and date entities for simple contradiction checks."""
        entities = set()
        for match in self.numeric_pattern.findall(text):
            entities.add(match.lower())
        for match in self.date_pattern.findall(text):
            entities.add(match.lower())
        return entities

    def analyze(self, candidates: list[ReliableCandidateDTO]) -> ContradictionReportDTO:
        """Scan pairs of candidates for mutually exclusive factual claims."""
        if len(candidates) < 2:
            return ContradictionReportDTO(contradiction_score=0.0, contradictory_pairs=[])
            
        contradictory_pairs = []
        max_conflict_score = 0.0
        
        # O(N^2) comparison of top-K chunks
        for c1, c2 in combinations(candidates, 2):
            # Extract basic entities
            e1 = self._extract_entities(c1.content)
            e2 = self._extract_entities(c2.content)
            
            # Simple heuristic: if chunks share a lot of words but differ in exact numbers/dates,
            # it might be a contradiction (e.g., "Revenue was 5M" vs "Revenue was 6M")
            words1 = set(re.findall(r'\b[a-z]{4,}\b', c1.content.lower()))
            words2 = set(re.findall(r'\b[a-z]{4,}\b', c2.content.lower()))
            
            word_overlap = len(words1.intersection(words2))
            if word_overlap > 1 and e1 and e2 and e1 != e2:
                # Potential conflict in specific numbers/dates while discussing the same topic
                conflict_score = 0.5
                if conflict_score > max_conflict_score:
                    max_conflict_score = conflict_score
                
                contradictory_pairs.append({
                    "chunk_id_1": str(c1.chunk_id),
                    "chunk_id_2": str(c2.chunk_id),
                    "reason": f"Mismatched entities in overlapping context: {e1} vs {e2}"
                })

        return ContradictionReportDTO(
            contradiction_score=max_conflict_score,
            contradictory_pairs=contradictory_pairs
        )
