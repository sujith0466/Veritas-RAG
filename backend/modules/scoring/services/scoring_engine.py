import os

from backend.modules.scoring.repositories.scoring_repository import ScoringRepository
from backend.modules.scoring.schemas.scoring_dto import ReliabilityScoreDTOv2, ScoringRequestDTO
from backend.modules.scoring.services.base_scorer import BaseReliabilityScorer
from backend.modules.scoring.services.penalty_calculator import PenaltyCalculator


class ScoringEngine:
    def __init__(self, repository: ScoringRepository):
        self.repository = repository
        self.base_scorer = BaseReliabilityScorer()
        self.penalty_calculator = PenaltyCalculator()

        self.trust_threshold = float(
            os.getenv("RAGUARD_SCORING_TRUST_THRESHOLD", "80.0")
        )

    async def calculate_score(
        self, request: ScoringRequestDTO
    ) -> ReliabilityScoreDTOv2:
        inputs = request.inputs

        # 1. Base Score
        base_score = self.base_scorer.calculate_base_score(inputs)

        # 2. Penalties
        penalty_deduction, penalty_breakdown = (
            self.penalty_calculator.calculate_penalty(inputs)
        )

        # 3. Final Score
        final_score = max(base_score - penalty_deduction, 0.0)

        # 4. Trust determination
        is_trusted = (
            final_score >= self.trust_threshold
            and inputs.unsupported_claim_count == 0
            and inputs.invalid_citation_count == 0
        )

        breakdown = {
            "inputs_used": inputs.model_dump(mode="json"),
            "base_score": base_score,
            "penalties": penalty_breakdown,
        }

        result = ReliabilityScoreDTOv2(
            correlation_id=request.correlation_id,
            tenant_id=request.tenant_id,
            final_score=final_score,
            base_score=base_score,
            penalty_deduction=penalty_deduction,
            is_trusted=is_trusted,
            breakdown=breakdown,
        )

        # 5. Save Telemetry
        await self.repository.save_log(result)

        return result
