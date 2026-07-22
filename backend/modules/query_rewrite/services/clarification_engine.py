"""ClarificationEngine — Phase 3 and Phase 9 orchestration engine.

Orchestrates query rewrite strategies to resolve ambiguity and optimize retrieval.
Supports full stateful clarification pauses and resumes (`Phase 9`).
"""

from structlog import get_logger

from backend.modules.query_rewrite.schemas.rewrite_dto import (
    ClarificationQuestionDTO, ClarificationResumeRequestDTO,
    ClarificationStateDTO, ClarifiedQueryDTO, RewriteRequestDTO,
    RewriteRequestDTOv2)
from backend.modules.query_rewrite.services.clarification_state_manager import \
    ClarificationStateManager
from backend.modules.query_rewrite.strategies.decomposition import \
    DecompositionRewriter
from backend.modules.query_rewrite.strategies.disambiguation import \
    DisambiguationRewriter
from backend.modules.query_rewrite.strategies.hyde import HyDERewriter

logger = get_logger(__name__)


class ClarificationEngine:
    """Orchestrates query rewrite strategies to resolve ambiguity and optimize retrieval."""

    def __init__(
        self,
        decomposition: DecompositionRewriter,
        hyde: HyDERewriter,
        disambiguation: DisambiguationRewriter,
        state_manager: ClarificationStateManager | None = None,
    ):
        self.decomposition = decomposition
        self.hyde = hyde
        self.disambiguation = disambiguation
        self.state_manager = state_manager or ClarificationStateManager()

    def rewrite_query(self, request: RewriteRequestDTO) -> dict:
        """Phase 3 baseline: Apply rewrite strategies and return a comprehensive rewrite package."""
        logger.info(f"ClarificationEngine processing query: {request.original_query}")

        # 1. Disambiguation Check
        clarification = self.disambiguation.generate_clarification(
            request.original_query
        )
        if clarification:
            logger.info("Query flagged as ambiguous; clarification required.")
            return {"status": "CLARIFICATION_REQUIRED", "clarification": clarification}

        # 2. Decomposition
        decomposed = self.decomposition.decompose(request.original_query)

        # 3. HyDE (Hypothetical Document Embeddings)
        hyde_resp = self.hyde.rewrite(request.original_query)

        return {"status": "REWRITTEN", "decomposed": decomposed, "hyde": hyde_resp}

    async def evaluate_and_clarify(
        self,
        request: RewriteRequestDTOv2,
        correlation_id: str,
    ) -> ClarificationQuestionDTO | None:
        """Phase 9: Evaluate query and confidence signals. If ambiguous, save state and return clarification question."""
        # Check disambiguation rewriter first
        clarification = self.disambiguation.generate_clarification(
            request.original_query
        )
        if clarification:
            logger.info(
                "Disambiguation triggered clarification", correlation_id=correlation_id
            )
            self.state_manager.save_state(
                correlation_id=correlation_id,
                tenant_id=request.tenant_id,
                original_query=request.original_query,
                question_text=clarification.question_text,
                options=clarification.options,
            )
            return clarification

        # Check confidence signals (e.g., low coverage + contradictory terms)
        if request.coverage_score is not None and request.coverage_score < 0.25:
            q_text = f"Your query '{request.original_query}' yielded low retrieval coverage ({request.coverage_score:.2f}). Could you specify what domain or module you are referring to?"
            opts = [
                "Authentication / Security",
                "Database / Storage",
                "API / Routing",
                "General Setup",
            ]
            clarification = ClarificationQuestionDTO(question_text=q_text, options=opts)
            self.state_manager.save_state(
                correlation_id=correlation_id,
                tenant_id=request.tenant_id,
                original_query=request.original_query,
                question_text=q_text,
                options=opts,
            )
            return clarification

        return None

    async def resume_clarification(
        self,
        resume_req: ClarificationResumeRequestDTO,
    ) -> ClarifiedQueryDTO:
        """Phase 9: Resume execution with user's selected clarification choice."""
        logger.info("Resuming clarification", correlation_id=resume_req.correlation_id)
        return self.state_manager.resolve_state(resume_req)

    def get_state(self, correlation_id: str) -> ClarificationStateDTO | None:
        """Retrieve pending or resolved clarification state."""
        return self.state_manager.get_state(correlation_id)
