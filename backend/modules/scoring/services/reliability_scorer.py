from backend.modules.scoring.schemas.scoring_dto import ReliabilityScoreDTO
from backend.modules.confidence.schemas.confidence_dto import ConfidenceResultDTO
from backend.modules.reflection.schemas.reflection_dto import ReflectionResultDTO
from backend.modules.retry.schemas.retry_dto import RetryContextDTO


class ReliabilityScorer:
    """Computes the unified reliability score from all Phase 3 pipeline signals.

    Score formula (0-100):
      - Confidence contribution: 40% weight
      - Grounding contribution (1 - hallucination_score): 40% weight
      - Retry efficiency contribution: 20% weight (fewer retries = better)
    """

    def compute(
        self,
        confidence_result: ConfidenceResultDTO,
        reflection_result: ReflectionResultDTO,
        retry_context: RetryContextDTO,
        is_fully_grounded: bool
    ) -> ReliabilityScoreDTO:
        """Compute the composite reliability score."""

        confidence_score = confidence_result.score  # 0-100
        hallucination_score = reflection_result.hallucination_score  # 0-1
        retry_attempts = len(retry_context.attempts)
        max_retries = retry_context.max_retries

        # Retry efficiency: 100 on zero retries, decreasing linearly
        retry_efficiency = max(0.0, 1.0 - (retry_attempts / (max_retries + 1)))

        # Composite (normalized to 0-100)
        final_score = (
            (confidence_score * 0.40) +
            ((1.0 - hallucination_score) * 100.0 * 0.40) +
            (retry_efficiency * 100.0 * 0.20)
        )
        final_score = max(0.0, min(100.0, final_score))

        return ReliabilityScoreDTO(
            final_score=final_score,
            confidence_score=confidence_score,
            hallucination_score=hallucination_score,
            is_fully_grounded=is_fully_grounded,
            is_safe_to_serve=reflection_result.is_safe_to_serve,
            retry_attempts=retry_attempts
        )
