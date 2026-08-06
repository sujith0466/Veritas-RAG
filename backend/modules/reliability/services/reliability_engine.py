import re

from backend.modules.retrieval.schemas.retrieval_dto import RankedEvidenceDTO


class ReliabilityEngine:
    """Incremental Reliability Engine for F8.7."""
    def __init__(self):
        self.ema_alpha = 0.3
        self.current_score = 1.0

    async def evaluate_incremental(self, sentence: str, evidence: list[RankedEvidenceDTO]) -> float:
        """
        Evaluate a single sentence against the evidence.
        Uses a fast Jaccard/overlap heuristic to approximate reliability.
        Returns the new Exponential Moving Average score.
        """
        if not evidence:
            return self.current_score

        # Fast normalization
        sent_words = set(re.findall(r'\b\w+\b', sentence.lower()))
        if not sent_words:
            return self.current_score

        best_overlap = 0.0
        for chunk in evidence:
            content = chunk.content if hasattr(chunk, "content") else chunk.get("content", "")
            ev_words = set(re.findall(r'\b\w+\b', str(content).lower()))
            if not ev_words:
                continue
            overlap = len(sent_words & ev_words) / len(sent_words)
            best_overlap = max(best_overlap, overlap)

        # Scale overlap to a reasonable reliability proxy (0.7 - 1.0)
        sentence_reliability = min(1.0, 0.7 + (best_overlap * 0.3))

        # EMA
        self.current_score = (self.ema_alpha * sentence_reliability) + ((1 - self.ema_alpha) * self.current_score)
        return self.current_score
