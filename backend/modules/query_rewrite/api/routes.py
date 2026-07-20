"""Query Rewrite REST API routes — Phase 8."""

from fastapi import APIRouter
from backend.modules.query_rewrite.schemas.rewrite_dto import (
    RewriteRequestDTOv2,
    RewriteResultDTO,
)
from backend.modules.query_rewrite.services.rewrite_orchestrator import RewriteOrchestrator

router = APIRouter()
_orchestrator = RewriteOrchestrator()


@router.post("/rewrite", response_model=RewriteResultDTO, summary="Rewrite query using optimal strategy")
async def rewrite_query(request: RewriteRequestDTOv2) -> RewriteResultDTO:
    """Select and execute the optimal query rewrite strategy based on confidence signals."""
    return _orchestrator.rewrite(request)


@router.get("/strategies", response_model=list[str], summary="List available rewrite strategies")
async def list_strategies() -> list[str]:
    """Return all available rewrite strategy names."""
    return _orchestrator.get_available_strategies()


@router.get("/history", response_model=list[RewriteResultDTO], summary="Get recent rewrite history")
async def get_rewrite_history(limit: int = 50) -> list[RewriteResultDTO]:
    """Return audit logs of recent query rewrites."""
    return _orchestrator.get_history(limit=limit)


# ---------------------------------------------------------------------------
# Phase 9 — Clarification Engine REST API routes
# ---------------------------------------------------------------------------
from typing import Optional
from fastapi import HTTPException
from backend.modules.query_rewrite.schemas.rewrite_dto import (
    ClarificationQuestionDTO,
    ClarificationResumeRequestDTO,
    ClarifiedQueryDTO,
    ClarificationStateDTO,
)
from backend.modules.query_rewrite.strategies.decomposition import DecompositionRewriter
from backend.modules.query_rewrite.strategies.hyde import HyDERewriter
from backend.modules.query_rewrite.strategies.disambiguation import DisambiguationRewriter
from backend.modules.query_rewrite.services.clarification_engine import ClarificationEngine
from backend.modules.query_rewrite.schemas.errors import ClarificationGenerationFailed

# Global instance for Phase 9 clarification endpoints
_clarification_engine = ClarificationEngine(
    decomposition=DecompositionRewriter(),
    hyde=HyDERewriter(),
    disambiguation=DisambiguationRewriter(),
)


@router.post("/clarify/evaluate", response_model=Optional[ClarificationQuestionDTO], summary="Evaluate if query requires clarification")
async def evaluate_clarification(request: RewriteRequestDTOv2, correlation_id: str) -> Optional[ClarificationQuestionDTO]:
    """Check if query requires user clarification and record paused state if needed."""
    return await _clarification_engine.evaluate_and_clarify(request, correlation_id=correlation_id)


@router.post("/clarify/resume", response_model=ClarifiedQueryDTO, summary="Resume paused execution with user clarification choice")
async def resume_clarification(resume_req: ClarificationResumeRequestDTO) -> ClarifiedQueryDTO:
    """Merge user choice and return resolved query for pipeline resumption."""
    try:
        return await _clarification_engine.resume_clarification(resume_req)
    except ClarificationGenerationFailed as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/clarify/state/{correlation_id}", response_model=Optional[ClarificationStateDTO], summary="Get active clarification state")
async def get_clarification_state(correlation_id: str) -> Optional[ClarificationStateDTO]:
    """Retrieve the current status and options of a clarification request."""
    state = _clarification_engine.get_state(correlation_id)
    if not state:
        raise HTTPException(status_code=404, detail="Clarification state not found.")
    return state
