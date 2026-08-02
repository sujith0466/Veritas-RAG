import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

# ---------------------------------------------------------------------------
# Milestone 13.3: Scoring Engine & APIs
# ---------------------------------------------------------------------------

def main():
    print("Starting Milestone 13.3 Implementation...")

    # 1. scoring_engine.py
    engine_path = "backend/modules/scoring/services/scoring_engine.py"
    if not os.path.exists(engine_path):
        with open(engine_path, "w") as f:
            f.write("""import os
from backend.modules.scoring.schemas.scoring_dto import ScoringRequestDTO, ReliabilityScoreDTO
from backend.modules.scoring.services.base_scorer import BaseReliabilityScorer
from backend.modules.scoring.services.penalty_calculator import PenaltyCalculator
from backend.modules.scoring.repositories.scoring_repository import ScoringRepository

class ScoringEngine:
    def __init__(self, repository: ScoringRepository):
        self.repository = repository
        self.base_scorer = BaseReliabilityScorer()
        self.penalty_calculator = PenaltyCalculator()
        
        self.trust_threshold = float(os.getenv("RAGUARD_SCORING_TRUST_THRESHOLD", "80.0"))

    async def calculate_score(self, request: ScoringRequestDTO) -> ReliabilityScoreDTO:
        inputs = request.inputs
        
        # 1. Base Score
        base_score = self.base_scorer.calculate_base_score(inputs)
        
        # 2. Penalties
        penalty_deduction, penalty_breakdown = self.penalty_calculator.calculate_penalty(inputs)
        
        # 3. Final Score
        final_score = max(base_score - penalty_deduction, 0.0)
        
        # 4. Trust determination
        is_trusted = (
            final_score >= self.trust_threshold and 
            inputs.unsupported_claim_count == 0 and 
            inputs.invalid_citation_count == 0
        )
        
        breakdown = {
            "inputs_used": inputs.model_dump(mode="json"),
            "base_score": base_score,
            "penalties": penalty_breakdown
        }
        
        result = ReliabilityScoreDTO(
            correlation_id=request.correlation_id,
            tenant_id=request.tenant_id,
            final_score=final_score,
            base_score=base_score,
            penalty_deduction=penalty_deduction,
            is_trusted=is_trusted,
            breakdown=breakdown
        )
        
        # 5. Save Telemetry
        await self.repository.save_log(result)
        
        return result
""")
        print("Created scoring_engine.py")

    # 2. api/routes.py
    with open("backend/modules/scoring/api/__init__.py", "w") as f:
        f.write('"""Scoring API routes."""\n')

    routes_path = "backend/modules/scoring/api/routes.py"
    if not os.path.exists(routes_path):
        with open(routes_path, "w") as f:
            f.write("""from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database.engine import get_db_session
from backend.modules.scoring.schemas.scoring_dto import ScoringRequestDTO, ReliabilityScoreDTO
from backend.modules.scoring.services.scoring_engine import ScoringEngine
from backend.modules.scoring.repositories.scoring_repository import ScoringRepository

router = APIRouter(prefix="/scoring/v1", tags=["Scoring"])

def get_scoring_engine(session: AsyncSession = Depends(get_db_session)) -> ScoringEngine:
    repo = ScoringRepository(session)
    return ScoringEngine(repo)

@router.post("/calculate", response_model=ReliabilityScoreDTO)
async def calculate_reliability_score(
    request: ScoringRequestDTO,
    engine: ScoringEngine = Depends(get_scoring_engine)
):
    try:
        return await engine.calculate_score(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
""")
        print("Created api/routes.py")

    print("Milestone 13.3 completed.")

if __name__ == "__main__":
    main()
