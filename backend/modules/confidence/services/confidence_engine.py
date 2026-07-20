from backend.modules.reliability.schemas.reliability_dto import ReliableRetrievalResultDTO
from backend.modules.confidence.schemas.confidence_dto import (
    ConfidenceEvalRequestDTO,
    ConfidenceResultDTO,
    ConfidenceAction,
    CoverageMetricsDTO,
    ContradictionReportDTO,
    FreshnessReportDTO
)
from backend.modules.confidence.services.coverage_analyzer import CoverageAnalyzer
from backend.modules.confidence.services.contradiction_detector import ContradictionDetector
from backend.modules.confidence.services.freshness_scorer import FreshnessScorer
import logging

logger = logging.getLogger(__name__)


import time
from backend.observability.metrics import (
    HALLUCINATION_DETECTIONS_TOTAL,
    record_confidence_metric,
    record_stage_duration,
)
from backend.observability.tracing import trace_confidence_evaluation


class ConfidenceEngine:
    """Pre-Generation Confidence & Hallucination Prevention Engine."""
    
    def __init__(
        self,
        coverage_analyzer: CoverageAnalyzer,
        contradiction_detector: ContradictionDetector,
        freshness_scorer: FreshnessScorer
    ):
        self.coverage_analyzer = coverage_analyzer
        self.contradiction_detector = contradiction_detector
        self.freshness_scorer = freshness_scorer
        
    def evaluate(self, request: ConfidenceEvalRequestDTO) -> ConfidenceResultDTO:
        """Evaluate evidence and compute deterministic threshold action."""
        start_time = time.perf_counter()
        retrieval_result = request.retrieval_result
        candidates = retrieval_result.candidates
        
        # 1. Run all scorers
        coverage: CoverageMetricsDTO = self.coverage_analyzer.analyze(request.query, candidates)
        contradiction: ContradictionReportDTO = self.contradiction_detector.analyze(candidates)
        freshness: FreshnessReportDTO = self.freshness_scorer.analyze(candidates)
        
        # 2. Evidence Density (Heuristic: are there enough candidates?)
        # For this baseline, if we got at least 3 candidates, density is 1.0
        density_score = min(1.0, len(candidates) / 3.0)
        
        # 3. Compute raw score (0-100)
        # Weights: Coverage (40%), Freshness (15%), Density (10%), Non-Contradiction (35%)
        raw_score = (
            (coverage.coverage_score * 40.0) +
            (freshness.freshness_score * 15.0) +
            (density_score * 10.0) +
            ((1.0 - contradiction.contradiction_score) * 35.0)
        )
        
        # Clamp score safely
        score = max(0.0, min(100.0, raw_score))
        
        # 4. Threshold Logic & Degraded Mode Adjustments
        # Default thresholds
        proceed_threshold = 75.0
        retry_threshold = 50.0
        
        # If the result came from a degraded fallback (e.g. circuit breaker tripped), 
        # we raise the standard for proceeding to ensure we don't hallucinate on weak BM25 data.
        if retrieval_result.is_degraded_fallback or retrieval_result.is_zero_result_broadened:
            proceed_threshold = 85.0
            retry_threshold = 60.0
            
        action = ConfidenceAction.ABORT
        if score >= proceed_threshold:
            action = ConfidenceAction.PROCEED
        elif score >= retry_threshold:
            action = ConfidenceAction.RETRY
        else:
            # If coverage is extremely low but contradiction is zero, it might just be ambiguity
            if coverage.coverage_score < 0.2 and contradiction.contradiction_score < 0.2:
                action = ConfidenceAction.CLARIFY
            else:
                action = ConfidenceAction.ABORT
                
        logger.info(f"ConfidenceEngine computed score={score:.2f} action={action} for query_id={retrieval_result.correlation_id}")
        
        duration = time.perf_counter() - start_time
        normalized_score = score / 100.0
        record_confidence_metric(normalized_score)
        record_stage_duration("confidence_evaluation", duration)
        if contradiction.contradiction_score > 0.5 or action == ConfidenceAction.ABORT:
            HALLUCINATION_DETECTIONS_TOTAL.labels(severity="high").inc()

        with trace_confidence_evaluation(
            score=normalized_score,
            is_grounded=action == ConfidenceAction.PROCEED,
            action=str(action),
            contradiction=contradiction.contradiction_score,
        ):
            return ConfidenceResultDTO(
                score=score,
                action=action,
                coverage_metrics=coverage,
                contradiction_report=contradiction,
                freshness_report=freshness,
                is_degraded=retrieval_result.is_degraded_fallback
            )

