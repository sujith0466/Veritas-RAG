import logging

from backend.modules.confidence.schemas.confidence_dto import ConfidenceEvalRequestDTO
from backend.modules.confidence.services.confidence_engine import ConfidenceEngine
from backend.modules.generation.schemas.generation_dto import GenerationRequestDTO
from backend.modules.generation.services.generation_service import GroundedGenerationService
from backend.modules.query_rewrite.schemas.rewrite_dto import RewriteRequestDTO
from backend.modules.query_rewrite.services.clarification_engine import ClarificationEngine
from backend.modules.reflection.schemas.reflection_dto import ReflectionRequestDTO
from backend.modules.reflection.services.reflection_engine import ReflectionEngine
from backend.modules.reliability.schemas.reliability_dto import ReliableRetrievalResultDTO
from backend.modules.retry.schemas.errors import MaxRetriesExceeded, NonMonotonicImprovement
from backend.modules.retry.services.state_machine import RetryStateMachine
from backend.modules.scoring.schemas.scoring_dto import (
    GatewayOutcome,
    GatewayRequestDTO,
    GatewayResponseDTO,
)
from backend.modules.scoring.services.reliability_scorer import ReliabilityScorer

logger = logging.getLogger(__name__)


class ExecutionGateway:
    """Unified Phase 3 Execution Gateway.

    Orchestrates the full self-correcting RAGuard pipeline:
      retrieval → confidence → [rewrite+retry loop] → generation → reflection → scoring
    """

    def __init__(
        self,
        confidence_engine: ConfidenceEngine,
        clarification_engine: ClarificationEngine,
        generation_service: GroundedGenerationService,
        reflection_engine: ReflectionEngine,
        reliability_scorer: ReliabilityScorer,
        max_retries: int = 2,
    ):
        self.confidence_engine = confidence_engine
        self.clarification_engine = clarification_engine
        self.generation_service = generation_service
        self.reflection_engine = reflection_engine
        self.reliability_scorer = reliability_scorer
        self.max_retries = max_retries

    def process(
        self, request: GatewayRequestDTO, retrieval_result: ReliableRetrievalResultDTO
    ) -> GatewayResponseDTO:
        """Run the complete Phase 3 pipeline for a single query."""

        correlation_id = request.correlation_id
        logger.info(
            f"[{correlation_id}] ExecutionGateway starting pipeline for query: {request.query}"
        )

        # Initialise retry state machine
        retry_sm = RetryStateMachine(
            correlation_id=correlation_id,
            original_query=request.query,
            max_retries=self.max_retries,
        )

        current_retrieval = retrieval_result
        current_query = request.query
        confidence_result = None
        rewrite_applied = False

        # ── Confidence → Retry Loop ──────────────────────────────────────────
        while True:
            retry_sm.record_retrieval_complete()

            # 1. Confidence Evaluation
            confidence_result = self.confidence_engine.evaluate(
                ConfidenceEvalRequestDTO(
                    query=current_query, retrieval_result=current_retrieval
                )
            )

            try:
                retry_sm.record_confidence_evaluation(
                    confidence_score=confidence_result.score,
                    action=confidence_result.action,
                    rewrite_applied=rewrite_applied,
                )
            except (MaxRetriesExceeded, NonMonotonicImprovement) as e:
                logger.warning(f"[{correlation_id}] Retry aborted: {e}")
                return GatewayResponseDTO(
                    correlation_id=correlation_id,
                    outcome=GatewayOutcome.ABORTED_MAX_RETRIES,
                    confidence_result=confidence_result,
                    retry_context=retry_sm.get_context(),
                    abort_reason=str(e),
                )

            from backend.modules.retry.schemas.retry_dto import RetryState

            state = retry_sm.state

            if state == RetryState.CLARIFICATION_REQUESTED:
                rewrite_result = self.clarification_engine.rewrite_query(
                    RewriteRequestDTO(original_query=current_query)
                )
                clarification_q = (
                    rewrite_result.get("clarification").question_text
                    if rewrite_result.get("clarification")
                    else None
                )
                return GatewayResponseDTO(
                    correlation_id=correlation_id,
                    outcome=GatewayOutcome.CLARIFICATION_REQUIRED,
                    confidence_result=confidence_result,
                    retry_context=retry_sm.get_context(),
                    clarification_question=clarification_q,
                )

            if state == RetryState.ABORTED:
                return GatewayResponseDTO(
                    correlation_id=correlation_id,
                    outcome=GatewayOutcome.ABORTED_LOW_CONFIDENCE,
                    confidence_result=confidence_result,
                    retry_context=retry_sm.get_context(),
                    abort_reason=f"Confidence score {confidence_result.score:.1f} too low",
                )

            if state == RetryState.RETRYING:
                # Apply query rewrite before next retrieval attempt
                rewrite_result = self.clarification_engine.rewrite_query(
                    RewriteRequestDTO(original_query=current_query)
                )
                if rewrite_result.get("hyde"):
                    current_query = rewrite_result["hyde"].embedding_query
                rewrite_applied = True
                # In a full system, the retrieval would be re-run here with current_query.
                # For the gateway test harness, retrieval_result is passed in and re-used.
                continue

            # state == GENERATING — proceed to answer generation
            break

        # ── Generation ────────────────────────────────────────────────────────
        evidence_chunks = [
            {
                "chunk_id": c.chunk_id,
                "document_id": c.document_id,
                "content": c.content,
                "score": (c.raw_rerank_score if hasattr(c, "raw_rerank_score") else getattr(c, "score", 0.0)),
            }
            for c in current_retrieval.candidates
        ]

        grounded_answer = self.generation_service.generate(
            GenerationRequestDTO(
                query=current_query,
                evidence_chunks=evidence_chunks,
                correlation_id=correlation_id,
            )
        )

        # ── Reflection ────────────────────────────────────────────────────────
        reflection_result = self.reflection_engine.reflect(
            ReflectionRequestDTO(
                grounded_answer=grounded_answer, correlation_id=correlation_id
            )
        )

        retry_sm.record_generation_complete()

        if not reflection_result.is_safe_to_serve:
            return GatewayResponseDTO(
                correlation_id=correlation_id,
                outcome=GatewayOutcome.ABORTED_HALLUCINATION,
                answer=grounded_answer,
                confidence_result=confidence_result,
                reflection_result=reflection_result,
                retry_context=retry_sm.get_context(),
                abort_reason=f"Hallucination score {reflection_result.hallucination_score:.2f} exceeds threshold",
            )

        # ── Reliability Scoring ───────────────────────────────────────────────
        reliability_score = self.reliability_scorer.compute(
            confidence_result=confidence_result,
            reflection_result=reflection_result,
            retry_context=retry_sm.get_context(),
            is_fully_grounded=grounded_answer.is_fully_grounded,
        )

        logger.info(
            f"[{correlation_id}] Pipeline complete. "
            f"reliability={reliability_score.final_score:.1f} safe={reflection_result.is_safe_to_serve}"
        )

        return GatewayResponseDTO(
            correlation_id=correlation_id,
            outcome=GatewayOutcome.SUCCESS,
            answer=grounded_answer,
            reliability_score=reliability_score,
            confidence_result=confidence_result,
            reflection_result=reflection_result,
            retry_context=retry_sm.get_context(),
        )
