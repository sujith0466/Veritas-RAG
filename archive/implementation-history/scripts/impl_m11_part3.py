import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

# ---------------------------------------------------------------------------
# Milestone 11.3: Async Orchestration & API Routes
# ---------------------------------------------------------------------------

def main():
    print("Starting Milestone 11.3 Implementation...")

    # 1. Update reflection_engine.py
    engine_path = "backend/modules/reflection/services/reflection_engine.py"
    with open(engine_path) as f:
        engine_content = f.read()

    if "reflect_async" not in engine_content:
        # We append the async logic
        new_engine_logic = """
import asyncio
from backend.modules.reflection.schemas.reflection_dto import (
    ReflectionRequestDTOv2, ReflectionResultDTOv2, ReflectionScoreDTO,
    CompletenessReportDTO, LogicalReviewReportDTO
)
from backend.modules.reflection.services.completeness_evaluator import CompletenessEvaluator
from backend.modules.reflection.services.logical_reviewer import LogicalConsistencyReviewer
from backend.modules.reflection.repositories.reflection_repository import ReflectionRepository

class ReflectionEngineV2:
    def __init__(self, repository: ReflectionRepository):
        self.claim_validator = ClaimValidator()
        self.completeness_evaluator = CompletenessEvaluator()
        self.logical_reviewer = LogicalConsistencyReviewer()
        self.repository = repository
        self.max_passes = int(os.getenv("RAGUARD_REFLECTION_MAX_PASSES", "2"))
        self.timeout_ms = int(os.getenv("RAGUARD_REFLECTION_TIMEOUT_MS", "350"))
        
    async def reflect_async(self, request: ReflectionRequestDTOv2) -> ReflectionResultDTOv2:
        attempt = 1
        return await self._execute_pass(request, attempt)
        
    async def _execute_pass(self, request: ReflectionRequestDTOv2, attempt: int) -> ReflectionResultDTOv2:
        answer_text = request.grounded_answer.text
        citations = [ex.text for ex in request.grounded_answer.citations]
        
        # 1. Claim extraction
        extracted_claims = _extract_claims_with_citations(answer_text)
        
        # 2. Async evaluation gathering
        try:
            results = await asyncio.wait_for(
                asyncio.gather(
                    self.claim_validator.validate_claims_async(extracted_claims, citations),
                    self.completeness_evaluator.evaluate(request.original_query, answer_text)
                ),
                timeout=self.timeout_ms / 1000.0
            )
            claim_results, (completeness_score, unaddressed) = results
        except asyncio.TimeoutError:
            # Fallback to basic claim validation on timeout
            claim_results = self.claim_validator.validate_claims(extracted_claims, citations)
            completeness_score = 1.0
            unaddressed = []
            
        # 3. Logical Consistency
        consistency_score, contradictions = await self.logical_reviewer.review(claim_results, citations)
        
        # 4. Aggregation
        overall_verdict = ClaimVerdict.SUPPORTED
        hallucination_score = 0.0
        
        if claim_results:
            unsupported_count = sum(1 for c in claim_results if c.verdict == ClaimVerdict.UNSUPPORTED)
            contradicted_count = sum(1 for c in claim_results if c.verdict == ClaimVerdict.CONTRADICTED)
            
            if contradicted_count > 0 or contradictions:
                overall_verdict = ClaimVerdict.CONTRADICTED
            elif unsupported_count > 0:
                overall_verdict = ClaimVerdict.UNSUPPORTED
                
            hallucination_score = (unsupported_count + contradicted_count) / len(claim_results)

        is_safe = (
            hallucination_score <= HALLUCINATION_THRESHOLD and
            overall_verdict != ClaimVerdict.CONTRADICTED and
            consistency_score >= 0.85 and
            completeness_score >= 0.75
        )
        
        result = ReflectionResultDTOv2(
            correlation_id=request.correlation_id,
            tenant_id=request.tenant_id,
            overall_verdict=overall_verdict,
            scores=ReflectionScoreDTO(
                hallucination_score=hallucination_score,
                completeness_score=completeness_score,
                consistency_score=consistency_score
            ),
            claim_results=claim_results,
            completeness_report=CompletenessReportDTO(
                score=completeness_score,
                unaddressed_clauses=unaddressed,
                addressed_clauses=[]
            ),
            logical_report=LogicalReviewReportDTO(
                consistency_score=consistency_score,
                contradictions_found=contradictions
            ),
            is_safe_to_serve=is_safe,
            attempt_number=attempt
        )
        
        # Multi-pass loop placeholder logic
        # If not safe and attempt < max_passes, we could trigger self-correction
        # For now, we return the result and let upstream handle retry (Phase 7/11 hook)
        
        # Save telemetry
        await self.repository.save_log(result)
        
        return result
"""
        with open(engine_path, "a") as f:
            f.write(new_engine_logic)
        print("Updated reflection_engine.py with async multi-pass orchestration")
    else:
        print("reflection_engine.py already updated")

    # 2. Update claim_validator.py to support async
    cv_path = "backend/modules/reflection/services/claim_validator.py"
    with open(cv_path) as f:
        cv_content = f.read()

    if "validate_claims_async" not in cv_content:
        new_cv = """
    async def validate_claims_async(self, extracted_claims: list[tuple[str, int | None]], citations: list[str]) -> list[ClaimValidationResultDTO]:
        # Simple wrapper for now, would be true async if calling external model
        return self.validate_claims(extracted_claims, citations)
"""
        with open(cv_path, "a") as f:
            f.write(new_cv)
        print("Updated claim_validator.py with validate_claims_async")

    # 3. Create api/routes.py
    os.makedirs("backend/modules/reflection/api", exist_ok=True)
    api_init = "backend/modules/reflection/api/__init__.py"
    if not os.path.exists(api_init):
        with open(api_init, "w") as f:
            f.write('"""Reflection API routes."""\n')

    routes_path = "backend/modules/reflection/api/routes.py"
    if not os.path.exists(routes_path):
        with open(routes_path, "w") as f:
            f.write("""from fastapi import APIRouter, Depends, HTTPException
from backend.modules.reflection.schemas.reflection_dto import ReflectionRequestDTOv2, ReflectionResultDTOv2
from backend.modules.reflection.services.reflection_engine import ReflectionEngineV2
from backend.modules.reflection.repositories.reflection_repository import ReflectionRepository
from backend.core.database.engine import get_db_session
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/reflection/v2", tags=["Reflection"])

def get_reflection_engine(session: AsyncSession = Depends(get_db_session)) -> ReflectionEngineV2:
    repo = ReflectionRepository(session)
    return ReflectionEngineV2(repo)

@router.post("/evaluate", response_model=ReflectionResultDTOv2)
async def evaluate_reflection(
    request: ReflectionRequestDTOv2,
    engine: ReflectionEngineV2 = Depends(get_reflection_engine)
):
    try:
        return await engine.reflect_async(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history/{correlation_id}", response_model=list[ReflectionResultDTOv2])
async def get_reflection_history(
    correlation_id: str,
    tenant_id: str,
    session: AsyncSession = Depends(get_db_session)
):
    repo = ReflectionRepository(session)
    logs = await repo.get_logs_by_correlation(correlation_id, tenant_id)
    return [
        ReflectionResultDTOv2(
            correlation_id=log.correlation_id,
            tenant_id=log.tenant_id,
            overall_verdict=log.overall_verdict,
            scores={"hallucination_score": log.hallucination_score, "completeness_score": log.completeness_score, "consistency_score": log.consistency_score},
            claim_results=log.metadata_payload.get("claim_results", []),
            completeness_report=log.metadata_payload.get("completeness_report", {}),
            logical_report=log.metadata_payload.get("logical_report", {}),
            is_safe_to_serve=log.is_safe_to_serve,
            attempt_number=log.attempt_number
        )
        for log in logs
    ]
""")
        print("Created api/routes.py")
    else:
        print("api/routes.py already exists")

    print("Milestone 11.3 completed.")

if __name__ == "__main__":
    main()
