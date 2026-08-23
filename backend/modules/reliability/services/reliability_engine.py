import re
from typing import Any

from backend.modules.retrieval.schemas.retrieval_dto import RankedEvidenceDTO
from backend.modules.scoring.schemas.scoring_dto import ScoringInputsDTO
from backend.modules.scoring.services.base_scorer import BaseReliabilityScorer
from backend.modules.scoring.services.penalty_calculator import PenaltyCalculator

_STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "and", "or", "in", "on",
    "of", "to", "for", "with", "that", "this", "it", "by", "as", "at", "from",
    "be", "have", "has", "had", "not", "but", "what", "which", "who", "when"
}


class ReliabilityEngine:
    """Deterministic incremental reliability evaluator for streaming response validation (F8.7)."""

    def __init__(
        self,
        llm_provider: Any | None = None,
        base_scorer: BaseReliabilityScorer | None = None,
        penalty_calculator: PenaltyCalculator | None = None,
        ema_alpha: float = 0.3,
    ) -> None:
        self.ema_alpha = ema_alpha
        self.current_score = 1.0
        self.llm_provider = llm_provider  # Preserved for backward-compatibility; no circular LLM calls
        self.base_scorer = base_scorer or BaseReliabilityScorer()
        self.penalty_calculator = penalty_calculator or PenaltyCalculator()

    async def evaluate_incremental(
        self, sentence: str, evidence: list[RankedEvidenceDTO]
    ) -> float:
        """
        Evaluate a single streamed sentence against evidence chunks using deterministic scoring.
        Updates and returns the Exponential Moving Average (EMA) reliability score.
        """
        if not sentence:
            return round(self.current_score, 4)

        words = re.findall(r'\b[a-zA-Z0-9_-]+\b', sentence.lower())
        content_words = [w for w in words if w not in _STOP_WORDS]

        # Sentence is too short to warrant penalty
        if len(content_words) < 2 or not evidence:
            return round(self.current_score, 4)

        # Aggregate evidence text and tokens
        evidence_tokens: set[str] = set()
        for chunk in evidence:
            chunk_content = (
                chunk.content if hasattr(chunk, "content")
                else (chunk.get("content", "") if isinstance(chunk, dict) else "")
            )
            if chunk_content:
                evidence_tokens.update(re.findall(r'\b[a-zA-Z0-9_-]+\b', chunk_content.lower()))

        if not evidence_tokens:
            return round(self.current_score, 4)

        # Compute lexical overlap ratio
        matched_tokens = sum(1 for w in content_words if w in evidence_tokens)
        coverage_ratio = matched_tokens / max(1, len(content_words))

        # Evidence relevance aggregation
        relevance_scores = [
            getattr(c, "normalized_relevance_score", 0.9)
            if hasattr(c, "normalized_relevance_score") and getattr(c, "normalized_relevance_score", None) is not None
            else 0.85
            for c in evidence[:3]
        ]
        avg_relevance = sum(relevance_scores) / max(1, len(relevance_scores))

        # Re-use authoritative ISS-006 scoring inputs
        inputs = ScoringInputsDTO(
            retrieval_relevance_score=max(0.0, min(1.0, float(avg_relevance))),
            validation_entailment_ratio=round(min(1.0, coverage_ratio), 4),
            confidence_evidence_strength=min(1.0, len(evidence) / 5.0),
            reflection_completeness=1.0 if coverage_ratio >= 0.5 else 0.5,
            unsupported_claim_count=0 if coverage_ratio >= 0.5 else 1,
            invalid_citation_count=0,
        )

        base_score = self.base_scorer.calculate_base_score(inputs)
        penalty_deduction, _ = self.penalty_calculator.calculate_penalty(inputs)
        sentence_reliability = max(0.0, min(1.0, (base_score - penalty_deduction) / 100.0))

        # Update Exponential Moving Average (EMA)
        self.current_score = (self.ema_alpha * sentence_reliability) + ((1.0 - self.ema_alpha) * self.current_score)
        return round(max(0.0, min(1.0, self.current_score)), 4)
