import os


def write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Created {path}")

# 1. Schemas
confidence_dto = '''"""Data Transfer Objects (`DTOs`) for the Confidence Engine."""

from pydantic import BaseModel, Field, ConfigDict
from enum import StrEnum
from backend.modules.reliability.schemas.reliability_dto import ReliableRetrievalResultDTO
import datetime

class ConfidenceAction(StrEnum):
    PROCEED = "PROCEED"
    RETRY = "RETRY"
    CLARIFY = "CLARIFY"
    ABORT = "ABORT"

class ConfidenceEvalRequestDTOv2(BaseModel):
    query: str = Field(..., description="The user's query to evaluate evidence against")
    retrieval_result: ReliableRetrievalResultDTO = Field(..., description="The reliable retrieval result containing evidence and SLA flags")
    tenant_id: str = Field(..., description="Tenant namespace ID")
    model_config = ConfigDict(from_attributes=True)

class ClauseCoverageDTO(BaseModel):
    clause: str
    token_overlap_score: float
    semantic_score: float | None = None
    model_config = ConfigDict(from_attributes=True)

class CoverageMetricsDTOv2(BaseModel):
    clause_coverage: list[ClauseCoverageDTO]
    overall_coverage_score: float = Field(..., ge=0.0, le=1.0)
    uncovered_clauses: list[str]
    coverage_method: str = Field(..., description="token | semantic | hybrid")
    model_config = ConfigDict(from_attributes=True)

class EvidenceStrengthDTO(BaseModel):
    strength_score: float = Field(..., ge=0.0, le=1.0)
    source_authority_score: float = Field(..., ge=0.0, le=1.0)
    corroboration_score: float = Field(..., ge=0.0, le=1.0)
    citation_density_score: float = Field(..., ge=0.0, le=1.0)
    rerank_confidence_score: float = Field(..., ge=0.0, le=1.0)
    model_config = ConfigDict(from_attributes=True)

class FreshnessReportDTOv2(BaseModel):
    mean_freshness_score: float = Field(..., ge=0.0, le=1.0)
    per_chunk_freshness: list[float]
    oldest_document_days: int
    freshest_document_days: int
    decay_function_used: str
    model_config = ConfigDict(from_attributes=True)

class ConflictSeverity(StrEnum):
    MINOR = "MINOR"
    MODERATE = "MODERATE"
    SEVERE = "SEVERE"

class ConflictPairDTO(BaseModel):
    chunk_a: str
    chunk_b: str
    claim_a: str
    claim_b: str
    severity: ConflictSeverity
    nli_label: str | None = None
    model_config = ConfigDict(from_attributes=True)

class ConflictReportDTOv2(BaseModel):
    conflict_score: float = Field(..., ge=0.0, le=1.0)
    conflict_pairs: list[ConflictPairDTO]
    has_severe_conflict: bool
    model_config = ConfigDict(from_attributes=True)

class ConfidenceResultDTOv2(BaseModel):
    score: float = Field(..., ge=0.0, le=100.0)
    action: ConfidenceAction
    coverage: CoverageMetricsDTOv2
    strength: EvidenceStrengthDTO
    freshness: FreshnessReportDTOv2
    conflict: ConflictReportDTOv2
    is_degraded: bool
    model_config = ConfigDict(from_attributes=True)
'''
write_file("backend/modules/confidence/schemas/confidence_dto.py", confidence_dto)


# 2. Coverage Analyzer v2
coverage = '''"""Coverage Analyzer v2.

Evaluates how thoroughly the retrieved evidence covers the distinct clauses
of the user query using token overlap and semantic matching.
"""

import re
from backend.modules.confidence.schemas.confidence_dto import CoverageMetricsDTOv2, ClauseCoverageDTO
from backend.modules.retrieval.schemas.retrieval_dto import RankedEvidenceDTO

class CoverageAnalyzer:
    """Analyzes evidence coverage of query clauses."""
    
    def _extract_clauses(self, query: str) -> list[str]:
        # Split on conjunctions and punctuation
        delimiters = r"\\s+and\\s+|\\s+or\\s+|\\s+but\\s+|,|\\.|;|\\?"
        clauses = [c.strip() for c in re.split(delimiters, query, flags=re.IGNORECASE) if c.strip()]
        return clauses if clauses else [query.strip()]

    def _token_overlap(self, clause: str, all_content: str) -> float:
        clause_tokens = set(clause.lower().split())
        if not clause_tokens:
            return 1.0
        content_tokens = set(all_content.lower().split())
        overlap = clause_tokens.intersection(content_tokens)
        return len(overlap) / len(clause_tokens)

    def analyze(self, query: str, evidence: list[RankedEvidenceDTO]) -> CoverageMetricsDTOv2:
        clauses = self._extract_clauses(query)
        all_content = " ".join([e.compressed_content or e.content for e in evidence])
        
        clause_metrics = []
        uncovered = []
        scores = []
        
        for clause in clauses:
            score = self._token_overlap(clause, all_content)
            clause_metrics.append(ClauseCoverageDTO(
                clause=clause,
                token_overlap_score=score,
                semantic_score=None
            ))
            scores.append(score)
            if score < 0.5:
                uncovered.append(clause)
                
        overall = sum(scores) / len(scores) if scores else 0.0
        
        return CoverageMetricsDTOv2(
            clause_coverage=clause_metrics,
            overall_coverage_score=overall,
            uncovered_clauses=uncovered,
            coverage_method="token"
        )
'''
write_file("backend/modules/confidence/services/coverage_analyzer.py", coverage)


# 3. Evidence Strength Scorer
strength = '''"""Evidence Strength Scorer.

Evaluates multi-dimensional evidence quality signals: authority, corroboration, citation density, rerank.
"""

from backend.modules.confidence.schemas.confidence_dto import EvidenceStrengthDTO
from backend.modules.retrieval.schemas.retrieval_dto import RankedEvidenceDTO

class EvidenceStrengthScorer:
    """Evaluates intrinsic evidence strength."""

    def score(self, evidence: list[RankedEvidenceDTO], top_k_requested: int) -> EvidenceStrengthDTO:
        if not evidence:
            return EvidenceStrengthDTO(
                strength_score=0.0,
                source_authority_score=0.0,
                corroboration_score=0.0,
                citation_density_score=0.0,
                rerank_confidence_score=0.0
            )

        auth_score = 0.7  # Default
        
        corrob_score = 0.3 # Single source default
        if len(evidence) >= 3:
            corrob_score = 1.0
        elif len(evidence) >= 2:
            corrob_score = 0.7
            
        citation_density = min(1.0, len(evidence) / top_k_requested) if top_k_requested > 0 else 1.0
        
        rerank_scores = [e.rerank_score for e in evidence if e.rerank_score is not None]
        rerank_conf = sum(rerank_scores) / len(rerank_scores) if rerank_scores else 0.5
        
        strength = (
            auth_score * 0.3 +
            corrob_score * 0.3 +
            citation_density * 0.2 +
            rerank_conf * 0.2
        )
        
        return EvidenceStrengthDTO(
            strength_score=strength,
            source_authority_score=auth_score,
            corroboration_score=corrob_score,
            citation_density_score=citation_density,
            rerank_confidence_score=rerank_conf
        )
'''
write_file("backend/modules/confidence/services/evidence_strength_scorer.py", strength)

print("impl_m6 part 1 completed.")
