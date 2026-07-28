# phase-6-implementation-plan.md
# RAGuard AI — Phase 6: Retrieval Reliability & Confidence Engine (Production Grade)

**Version**: 1.0.0  
**Date**: 2026-07-20  
**Author**: Principal Software Architect  
**Status**: PLANNING — Awaiting Approval  
**Depends On**: Phase 5 (Hybrid Retrieval)

---

## 1. Executive Summary

Phase 6 delivers the **production-grade Retrieval Reliability & Confidence Engine**, which sits between the Hybrid Retrieval Engine (Phase 5) and the Retry Controller (Phase 7). Its responsibility is to evaluate the quality, sufficiency, and trustworthiness of retrieved evidence *before* any LLM generation is invoked.

While Phase 3 introduced baseline `ConfidenceEngine`, `CoverageAnalyzer`, `ContradictionDetector`, and `FreshnessScorer` stubs, Phase 6 promotes these to production quality: configurable weights, multi-signal evidence strength scoring, conflict detection with contradiction severity grading, freshness decay curves, and REST API exposure.

The Confidence Engine outputs a structured `ConfidenceResultDTOv2` consumed by Phase 7's Retry Controller, Phase 8's Query Rewrite, and Phase 9's Clarification Engine.

---

## 2. Phase Objectives

1. Productionize **Coverage Analyzer** — clause-level query coverage assessment via NLP term overlap and semantic matching.
2. Implement **Evidence Strength Scorer** — multi-dimensional scoring including source authority, document recency, citation density, and cross-source corroboration.
3. Productionize **Freshness Analyzer** — decay curves (linear, exponential, step-function), configurable recency windows, and per-tenant freshness policy.
4. Implement **Conflict Detection** — contradiction severity grading (MINOR / MODERATE / SEVERE), contradicted-claim pairs, and conflict confidence score.
5. Extend **Confidence Engine** — configurable weight matrix, degraded-mode threshold adjustments, and per-tenant confidence policy.
6. Expose **Confidence Assessment REST API** — evaluate evidence quality on-demand, inspect per-signal breakdowns.
7. Integrate with Phase 5's `RetrievalResultDTOv2` and `CompressedEvidenceDTO`.

---

## 3. Business Goals

- **Hallucination Prevention**: Catch insufficient or conflicting evidence *before* LLM generation, not after.
- **Explainability**: Every confidence decision comes with a detailed signal breakdown auditable by operators.
- **Configurability**: Per-tenant confidence policies allow domain-specific threshold tuning without code changes.
- **Reliability**: The confidence engine must not introduce latency > 50ms on top of the retrieval pipeline.
- **Traceability**: All confidence evaluations are logged and queryable for post-incident investigation.

---

## 4. Technical Goals

- Coverage analysis uses both token-level overlap (TF-IDF) and optional semantic similarity (embedding cosine).
- Evidence strength scoring is composable: each signal is independently scored and weighted.
- Freshness decay curves are pluggable (linear, exponential, step) per document type.
- Conflict detection uses NLI (Natural Language Inference) entailment signals where available, fallback to keyword contradiction heuristics.
- Confidence Engine computes a deterministic `score ∈ [0, 100]` and deterministic `action ∈ {PROCEED, RETRY, CLARIFY, ABORT}`.
- All five sub-engines are individually unit-testable and independently configurable.

---

## 5. Scope

| Component | Included in Phase 6 |
|---|---|
| Coverage Analyzer (production) | ✅ |
| Evidence Strength Scorer | ✅ |
| Freshness Analyzer (production, decay curves) | ✅ |
| Conflict Detection (NLI + heuristic) | ✅ |
| Confidence Engine (production, configurable weights) | ✅ |
| Confidence Assessment REST API | ✅ |
| Per-tenant Confidence Policy | ✅ |
| Confidence Assessment Log (DB) | ✅ |
| Unit + Integration Tests | ✅ |

---

## 6. Out of Scope

- Query rewriting / alternative query generation (→ Phase 8)
- Clarification question generation (→ Phase 9)
- LLM answer generation (→ Phase 10)
- Circuit breaker failover (already in Phase 2's `ReliabilityGateway`)
- Frontend UI components

---

## 7. PRD Alignment

| PRD Requirement | Phase 6 Component |
|---|---|
| FR-CE-1: Pre-generation grounding check | ConfidenceEngine |
| FR-CE-2: Coverage completeness scoring | CoverageAnalyzer (production) |
| FR-CE-3: Contradiction/conflict detection | ConflictDetector |
| FR-CE-4: Freshness / recency assessment | FreshnessAnalyzer (decay curves) |
| FR-CE-5: Confidence action routing | ConfidenceEngine (PROCEED/RETRY/CLARIFY/ABORT) |
| NFR-EXP-1: Explainable confidence decisions | ConfidenceResultDTOv2 (per-signal breakdown) |
| NFR-PERF-2: Confidence evaluation < 50ms | Async analyzers, no I/O in hot path |

---

## 8. Architecture Alignment

- Follows ADR-005: all confidence logic under `backend/modules/confidence/`.
- Follows ADR-006: NLI provider behind abstract interface in `backend/providers/nli/`.
- Phase 6 extends the existing `ConfidenceEngine` — it does NOT replace or duplicate it.

---

## 9. Dependency Analysis

### Upstream Dependencies
| Phase | Component | Required By Phase 6 |
|---|---|---|
| Phase 5 | `RetrievalResultDTOv2` + `CompressedEvidenceDTO` | Input to confidence evaluation |
| Phase 5 | `FilterDSL` | Document type metadata for freshness policy |
| Phase 3 | `ConfidenceEngine` (baseline stub) | Extension target |
| Phase 4 | OpenTelemetry Tracer | Span coverage |

### Downstream Consumers
| Phase | Component | Consumes from Phase 6 |
|---|---|---|
| Phase 7 | RetryController | `ConfidenceResultDTOv2` (action, score) |
| Phase 8 | QueryRewrite | `ConfidenceResultDTOv2` (low_coverage signal) |
| Phase 9 | ClarificationEngine | `ConfidenceResultDTOv2` (ambiguity signal) |
| Phase 10 | AnswerGenerator | `ConfidenceResultDTOv2` (proceed check) |

---

## 10. Existing Codebase Review

### What Already Exists (Baseline — DO NOT Duplicate)

| Component | Location | Status |
|---|---|---|
| `ConfidenceEngine` | `backend/modules/confidence/services/confidence_engine.py` | Phase 6 extends |
| `CoverageAnalyzer` | `backend/modules/confidence/services/coverage_analyzer.py` | Phase 6 productionizes |
| `ContradictionDetector` | `backend/modules/confidence/services/contradiction_detector.py` | Phase 6 replaces with ConflictDetector |
| `FreshnessScorer` | `backend/modules/confidence/services/freshness_scorer.py` | Phase 6 extends with decay curves |
| `ConfidenceEvalRequestDTO` | `backend/modules/confidence/schemas/confidence_dto.py` | Extend |
| `ConfidenceResultDTO` | Same | Replace with ConfidenceResultDTOv2 |
| `ConfidenceAction` | Same | Preserve |

---

## 11. High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│           Phase 6: Retrieval Reliability & Confidence Engine         │
├───────────────────────────────────┬──────────────────────────────────┤
│  /api/v1/confidence/evaluate      │  FastAPI Router                  │
│  /api/v1/confidence/policy        │  (Confidence Assessment API)     │
├───────────────────────────────────┴──────────────────────────────────┤
│                      ConfidenceEngine (v2)                           │
│                                                                      │
│  ┌─────────────────┐  ┌──────────────────┐  ┌────────────────────┐  │
│  │ CoverageAnalyzer│  │EvidenceStrength  │  │ FreshnessAnalyzer  │  │
│  │ (production v2) │  │Scorer            │  │ (decay curves)     │  │
│  └────────┬────────┘  └────────┬─────────┘  └─────────┬──────────┘  │
│           │                    │                       │             │
│           └────────────────────┼───────────────────────┘             │
│                                │                                     │
│           ┌────────────────────▼───────────────────────┐             │
│           │          ConflictDetector (v2)              │             │
│           │   NLI entailment + contradiction heuristics │             │
│           └────────────────────┬───────────────────────┘             │
│                                │                                     │
│           ┌────────────────────▼───────────────────────┐             │
│           │         Confidence Score Aggregator         │             │
│           │  weighted sum → score ∈ [0,100] → action   │             │
│           └────────────────────┬───────────────────────┘             │
│                                │                                     │
│                   ConfidenceResultDTOv2                              │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 12. Low-Level Design

### Coverage Analyzer (v2)

```
Input: query string + list[CompressedEvidenceDTO]

Stage 1 — Query Clause Extraction:
  Parse query into logical clauses using rule-based clause splitter
  (split on conjunctions: "and", "or", "but", commas for multi-part questions)
  → list[str] clauses

Stage 2 — Token Overlap Coverage (per clause):
  For each clause, compute:
    token_overlap = |clause_tokens ∩ all_evidence_tokens| / |clause_tokens|
  
Stage 3 — Semantic Coverage (optional, requires embedding provider):
  For each clause, compute cosine_similarity(embed(clause), embed(evidence_chunk))
  Use max similarity across all chunks as coverage signal

Stage 4 — Coverage Score:
  coverage_score = weighted_avg(token_overlap × 0.6 + semantic_coverage × 0.4)
  Normalized to [0.0, 1.0]

Output: CoverageMetricsDTOv2
  clause_coverage: list[ClauseCoverageDTO]
  overall_coverage_score: float
  uncovered_clauses: list[str]
  coverage_method: "token" | "semantic" | "hybrid"
```

### Evidence Strength Scorer (new)

```
Signals:
  1. source_authority: float [0,1]
     - Documents tagged as "authoritative" (via metadata): 1.0
     - Standard documents: 0.7
     - User-uploaded unverified: 0.4

  2. cross_source_corroboration: float [0,1]
     - Same claim appears in ≥3 documents: 1.0
     - ≥2 documents: 0.7
     - Single source: 0.3

  3. citation_density: float [0,1]
     - evidence_count / top_k_requested (bounded to [0,1])

  4. rerank_confidence: float [0,1]
     - Derived from average rerank_score of top evidence items

Aggregation:
  strength_score = (
    source_authority × 0.3 +
    cross_source_corroboration × 0.3 +
    citation_density × 0.2 +
    rerank_confidence × 0.2
  )

Output: EvidenceStrengthDTO
  strength_score: float
  source_authority_score: float
  corroboration_score: float
  citation_density_score: float
  rerank_confidence_score: float
```

### Freshness Analyzer (v2 — decay curves)

```
Input: list[CompressedEvidenceDTO] + FreshnessPolicy

FreshnessPolicy:
  recency_window_days: int = 365
  decay_function: "linear" | "exponential" | "step"
  step_boundaries: list[tuple[int, float]] (for step decay)
  weight: float = 0.15

Decay Functions:
  linear:      score = max(0, 1 - age_days / recency_window_days)
  exponential: score = exp(-lambda × age_days)  (lambda = ln(2)/half_life_days)
  step:        score = lookup(age_days, step_boundaries)

Per-chunk freshness score → aggregated mean freshness across top_k evidence.

Output: FreshnessReportDTOv2
  mean_freshness_score: float
  per_chunk_freshness: list[float]
  oldest_document_days: int
  freshest_document_days: int
  decay_function_used: str
```

### Conflict Detector (v2 — replaces ContradictionDetector)

```
Stage 1 — Claim Pair Extraction:
  For each pair of evidence chunks, extract conflicting sentence pairs
  using keyword antonym detection: ("increased", "decreased"), ("approved", "rejected"),
  ("supports", "contradicts"), numeric value conflicts.

Stage 2 — NLI Entailment Check (if NLI provider available):
  nli_label = NLIProvider.classify(premise, hypothesis)
  → ENTAILMENT | NEUTRAL | CONTRADICTION

Stage 3 — Severity Grading:
  MINOR:    keyword contradiction, no numeric conflict
  MODERATE: numeric value conflict, date conflict
  SEVERE:   NLI-confirmed CONTRADICTION or logical negation ("X is not Y" vs "X is Y")

Stage 4 — Conflict Score:
  conflict_score = 0.0
  for each conflict: conflict_score += severity_weight (MINOR=0.1, MODERATE=0.3, SEVERE=1.0)
  conflict_score = min(1.0, conflict_score / len(evidence_pairs))

Output: ConflictReportDTOv2
  conflict_score: float
  conflict_pairs: list[ConflictPairDTO]
    chunk_a: str, chunk_b: str, claim_a: str, claim_b: str,
    severity: ConflictSeverity, nli_label: str | None
  has_severe_conflict: bool
```

### Confidence Engine (v2 — configurable weights)

```
WeightMatrix (configurable per tenant via ConfidencePolicy):
  coverage_weight: float = 0.40
  evidence_strength_weight: float = 0.25
  freshness_weight: float = 0.15
  conflict_weight: float = 0.20

Score:
  raw_score = (
    coverage.overall_coverage_score × weight.coverage × 100 +
    strength.strength_score × weight.evidence_strength × 100 +
    freshness.mean_freshness_score × weight.freshness × 100 +
    (1 - conflict.conflict_score) × weight.conflict × 100
  )
  score = clamp(raw_score, 0.0, 100.0)

Threshold Logic:
  Base thresholds (configurable via ConfidencePolicy):
    proceed_threshold: float = 75.0
    retry_threshold: float = 50.0
    
  Degraded-mode adjustments:
    if retrieval_result.is_degraded_fallback: +10 to both thresholds
    if conflict.has_severe_conflict: force ABORT regardless of score

  Action Resolution:
    score ≥ proceed_threshold → PROCEED
    retry_threshold ≤ score < proceed_threshold → RETRY
    coverage.uncovered_clauses > 50% and conflict.conflict_score < 0.2 → CLARIFY
    else → ABORT
```

---

## 13. Component Design

### 13.1 CoverageAnalyzer (v2)
```
class CoverageAnalyzer:
  - analyze(query, evidence: list[CompressedEvidenceDTO], policy: CoveragePolicy) → CoverageMetricsDTOv2
  - _extract_clauses(query) → list[str]
  - _token_overlap_score(clause, all_content) → float
  - _semantic_coverage_score(clause, chunks) → float (optional)
  - _aggregate(clause_scores) → float
```

### 13.2 EvidenceStrengthScorer (new)
```
class EvidenceStrengthScorer:
  - score(evidence: list[CompressedEvidenceDTO]) → EvidenceStrengthDTO
  - _source_authority_score(metadata) → float
  - _cross_source_corroboration(evidence) → float
  - _citation_density(evidence_count, top_k) → float
  - _rerank_confidence(evidence) → float
```

### 13.3 FreshnessAnalyzer (v2)
```
class FreshnessAnalyzer:
  - analyze(evidence: list[CompressedEvidenceDTO], policy: FreshnessPolicy) → FreshnessReportDTOv2
  - _linear_decay(age_days, window_days) → float
  - _exponential_decay(age_days, half_life_days) → float
  - _step_decay(age_days, boundaries) → float
  - _compute_age(created_at: datetime) → int
```

### 13.4 ConflictDetector (v2)
```
class ConflictDetector:
  - analyze(evidence: list[CompressedEvidenceDTO], policy: ConflictPolicy) → ConflictReportDTOv2
  - _extract_conflict_pairs(chunks) → list[tuple[str,str]]
  - _keyword_contradiction_check(a, b) → ConflictSeverity | None
  - _numeric_conflict_check(a, b) → ConflictSeverity | None
  - _nli_entailment_check(a, b) → str | None (if NLI provider available)
  - _grade_severity(checks) → ConflictSeverity
```

### 13.5 ConfidenceEngine (v2)
```
class ConfidenceEngine:
  - evaluate(request: ConfidenceEvalRequestDTOv2) → ConfidenceResultDTOv2
  - _compute_raw_score(coverage, strength, freshness, conflict, weights) → float
  - _resolve_action(score, thresholds, conflict, coverage) → ConfidenceAction
  - _apply_degraded_mode_adjustments(thresholds, retrieval_result) → Thresholds
```

### 13.6 ConfidencePolicyStore (new)
```
class ConfidencePolicyStore:
  - get_policy(tenant_id: str) → ConfidencePolicy
  - set_policy(tenant_id: str, policy: ConfidencePolicy) → None
  - reset_to_default(tenant_id: str) → None
  # Backend: Redis (fast) + PostgreSQL (durable) with write-through caching
```

---

## 14. Module Responsibilities

| Component | Responsibility |
|---|---|
| `CoverageAnalyzer` | Measure query clause coverage in retrieved evidence |
| `EvidenceStrengthScorer` | Evaluate multi-dimensional evidence quality signals |
| `FreshnessAnalyzer` | Apply configurable decay curves to document recency |
| `ConflictDetector` | Identify and grade contradictions between evidence chunks |
| `ConfidenceEngine` | Aggregate all signals with weighted scoring; route action |
| `ConfidencePolicyStore` | Persist per-tenant weight/threshold configuration |
| `ConfidenceRepository` | Log all evaluations with full signal breakdown |
| API Routes | Expose evaluate and policy management endpoints |

---

## 15. Data Flow

```
Phase 5 Output (RetrievalResultDTOv2 + CompressedEvidenceDTO)
              │
              ▼
    ConfidenceEvalRequestDTOv2
    {query, retrieval_result, tenant_id, options}
              │
    ┌─────────┼──────────────────────────────────────┐
    │         │                                      │
    ▼         ▼                              ▼       ▼
CoverageAnalyzer  EvidenceStrengthScorer  FreshnessAnalyzer  ConflictDetector
    │         │                                      │       │
    └─────────┴──────────────────────────────────────┘───────┘
                              │
                    Confidence Score Aggregator
                    (weighted sum + threshold logic)
                              │
                    ConfidenceResultDTOv2
                    {score, action, per_signal_breakdown}
                              │
                ┌─────────────┼──────────────────┐
                │             │                  │
                ▼             ▼                  ▼
            Phase 7       Phase 8            Phase 9
           (RetryCtrl)  (QueryRewrite)   (Clarification)
```

---

## 16. Sequence Flow

```
1. Client → POST /api/v1/confidence/evaluate (or internal call from Phase 7)
2. ConfidencePolicyStore.get_policy(tenant_id) → ConfidencePolicy
3. Run all analyzers (can run concurrently for performance):
   a. CoverageAnalyzer.analyze(query, evidence, policy.coverage)
   b. EvidenceStrengthScorer.score(evidence)
   c. FreshnessAnalyzer.analyze(evidence, policy.freshness)
   d. ConflictDetector.analyze(evidence, policy.conflict)
4. ConfidenceEngine._compute_raw_score(results, weights)
5. ConfidenceEngine._resolve_action(score, thresholds, conflict, coverage)
6. Construct ConfidenceResultDTOv2
7. ConfidenceRepository.log_evaluation(result)
8. Emit domain event: CONFIDENCE_EVALUATED
9. Return ConfidenceResultDTOv2 to caller
```

---

## 17. Folder Structure Changes

```
backend/modules/confidence/
├── api/                           [NEW]
│   ├── __init__.py                [NEW]
│   ├── routes.py                  [NEW] evaluate + policy endpoints
│   └── dependencies.py            [NEW] policy store injection
├── schemas/
│   ├── __init__.py
│   ├── confidence_dto.py           [MODIFY] add v2 DTOs; extend existing
│   └── errors.py                  [MODIFY] add CNF_004 (PolicyNotFound)
├── services/
│   ├── confidence_engine.py        [MODIFY] v2 with configurable weights
│   ├── coverage_analyzer.py        [MODIFY] production v2 with clauses
│   ├── freshness_scorer.py         [MODIFY] v2 with decay curves → FreshnessAnalyzer
│   ├── contradiction_detector.py   [RENAME→] conflict_detector.py [MODIFY/EXTEND]
│   ├── evidence_strength_scorer.py [NEW]
│   └── confidence_policy_store.py  [NEW]
├── models/
│   ├── __init__.py                [NEW]
│   └── confidence_log.py           [NEW] ConfidenceEvaluationLog ORM model
├── repositories/
│   ├── __init__.py                [NEW]
│   └── confidence_repository.py    [NEW]
├── events/
│   ├── __init__.py                [NEW]
│   └── payloads.py                [NEW] ConfidenceEvaluatedPayload
└── workers/                       [optional — async logging only]

backend/providers/nli/             [NEW]
├── __init__.py                    [NEW]
├── base.py                        [NEW] BaseNLIProvider
└── heuristic_provider.py          [NEW] HeuristicNLIProvider (no external call)
```

---

## 18. File Creation Plan

| File | Type | Purpose |
|---|---|---|
| `schemas/confidence_dto.py` extensions | MODIFY | Add `ConfidenceEvalRequestDTOv2`, `ConfidenceResultDTOv2`, `CoverageMetricsDTOv2`, `EvidenceStrengthDTO`, `FreshnessReportDTOv2`, `ConflictReportDTOv2`, `ClauseCoverageDTO`, `ConflictPairDTO`, `ConflictSeverity` |
| `services/evidence_strength_scorer.py` | NEW | `EvidenceStrengthScorer` |
| `services/conflict_detector.py` | NEW | `ConflictDetector` (v2, extends contradiction detector) |
| `services/confidence_policy_store.py` | NEW | `ConfidencePolicyStore` |
| `models/confidence_log.py` | NEW | `ConfidenceEvaluationLog` ORM |
| `repositories/confidence_repository.py` | NEW | `ConfidenceRepository` |
| `events/payloads.py` | NEW | Domain events |
| `api/routes.py` | NEW | REST API for confidence evaluation and policy |
| `api/dependencies.py` | NEW | FastAPI dependencies |
| `backend/providers/nli/base.py` | NEW | `BaseNLIProvider` abstract |
| `backend/providers/nli/heuristic_provider.py` | NEW | `HeuristicNLIProvider` |
| `tests/unit/backend/modules/confidence/test_confidence_v2.py` | NEW | Phase 6 unit tests |

---

## 19. Database Changes

### Alembic Migration: `0010_confidence_v2_schema.py`

```sql
CREATE TABLE confidence_evaluation_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       VARCHAR(255) NOT NULL,
    correlation_id  VARCHAR(255) NOT NULL,
    query_text      TEXT NOT NULL,
    score           FLOAT NOT NULL,
    action          VARCHAR(50) NOT NULL,
    coverage_score  FLOAT NOT NULL,
    strength_score  FLOAT NOT NULL,
    freshness_score FLOAT NOT NULL,
    conflict_score  FLOAT NOT NULL,
    has_severe_conflict BOOLEAN DEFAULT FALSE,
    uncovered_clauses_count INTEGER DEFAULT 0,
    is_degraded     BOOLEAN DEFAULT FALSE,
    signal_breakdown_json JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_confidence_logs_tenant_correlation
    ON confidence_evaluation_logs(tenant_id, correlation_id);

CREATE INDEX idx_confidence_logs_action
    ON confidence_evaluation_logs(action, created_at DESC);

-- ConfidencePolicy per-tenant config table
CREATE TABLE confidence_policies (
    tenant_id                VARCHAR(255) PRIMARY KEY,
    coverage_weight          FLOAT NOT NULL DEFAULT 0.40,
    strength_weight          FLOAT NOT NULL DEFAULT 0.25,
    freshness_weight         FLOAT NOT NULL DEFAULT 0.15,
    conflict_weight          FLOAT NOT NULL DEFAULT 0.20,
    proceed_threshold        FLOAT NOT NULL DEFAULT 75.0,
    retry_threshold          FLOAT NOT NULL DEFAULT 50.0,
    freshness_window_days    INTEGER NOT NULL DEFAULT 365,
    freshness_decay_function VARCHAR(20) NOT NULL DEFAULT 'linear',
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## 20. API Design

### 20.1 POST /api/v1/confidence/evaluate

**Request** (`ConfidenceEvalRequestDTOv2`):
```json
{
  "query": "What is the revenue growth rate for Q3 2025?",
  "retrieval_result": { "...RetrievalResultDTOv2..." },
  "options": {
    "run_nli": false,
    "max_conflict_pairs": 10
  }
}
```

**Response** (`ConfidenceResultDTOv2`):
```json
{
  "score": 82.4,
  "action": "PROCEED",
  "coverage_metrics": {
    "overall_coverage_score": 0.87,
    "clause_coverage": [
      {"clause": "revenue growth rate", "score": 0.91, "covered_by": ["chunk-1", "chunk-3"]},
      {"clause": "Q3 2025", "score": 0.82, "covered_by": ["chunk-2"]}
    ],
    "uncovered_clauses": []
  },
  "evidence_strength": {
    "strength_score": 0.79,
    "source_authority_score": 0.85,
    "corroboration_score": 0.70,
    "citation_density_score": 1.0,
    "rerank_confidence_score": 0.88
  },
  "freshness_report": {
    "mean_freshness_score": 0.93,
    "oldest_document_days": 42,
    "freshest_document_days": 3,
    "decay_function_used": "exponential"
  },
  "conflict_report": {
    "conflict_score": 0.05,
    "has_severe_conflict": false,
    "conflict_pairs": []
  },
  "is_degraded": false,
  "weight_matrix_used": {
    "coverage": 0.40, "evidence_strength": 0.25, "freshness": 0.15, "conflict": 0.20
  }
}
```

### 20.2 GET /api/v1/confidence/policy

Returns current `ConfidencePolicy` for authenticated tenant.

### 20.3 PUT /api/v1/confidence/policy

Update `ConfidencePolicy` for authenticated tenant (admin role required).

### 20.4 GET /api/v1/confidence/history

Paginated `ConfidenceEvaluationLog` query for the authenticated tenant.

---

## 21. Configuration Changes

```python
class ConfidenceSettings(BaseModel):
    default_coverage_weight: float = 0.40
    default_strength_weight: float = 0.25
    default_freshness_weight: float = 0.15
    default_conflict_weight: float = 0.20
    default_proceed_threshold: float = 75.0
    default_retry_threshold: float = 50.0
    default_freshness_window_days: int = 365
    default_freshness_decay_function: str = "linear"
    nli_provider: str = "heuristic"  # heuristic | cohere | local
    max_conflict_pairs_evaluated: int = 20
    analyzer_timeout_ms: int = 50
```

---

## 22. Environment Variables

```bash
# Phase 6 Confidence Configuration
CONFIDENCE_DEFAULT_COVERAGE_WEIGHT=0.40
CONFIDENCE_DEFAULT_STRENGTH_WEIGHT=0.25
CONFIDENCE_DEFAULT_FRESHNESS_WEIGHT=0.15
CONFIDENCE_DEFAULT_CONFLICT_WEIGHT=0.20
CONFIDENCE_DEFAULT_PROCEED_THRESHOLD=75.0
CONFIDENCE_DEFAULT_RETRY_THRESHOLD=50.0
CONFIDENCE_DEFAULT_FRESHNESS_WINDOW_DAYS=365
CONFIDENCE_DEFAULT_FRESHNESS_DECAY_FUNCTION=linear
CONFIDENCE_NLI_PROVIDER=heuristic
CONFIDENCE_MAX_CONFLICT_PAIRS=20
CONFIDENCE_ANALYZER_TIMEOUT_MS=50
```

---

## 23. Security Considerations

1. **Per-Tenant Policy Isolation**: `ConfidencePolicy` is scoped per `tenant_id`; admin-role JWT required for updates.
2. **No Cross-Tenant Evaluation**: `ConfidenceEvaluationLog` has `tenant_id` with database-level row filtering.
3. **NLI Provider Constraints**: Heuristic provider makes no external network calls — no data leaves the system.
4. **Policy Injection Prevention**: Weight values are Pydantic-constrained to `[0.0, 1.0]`; weight sum validated to approximately 1.0.
5. **Audit Log Integrity**: `ConfidenceEvaluationLog` records are append-only (no UPDATE/DELETE endpoints).

---

## 24. Performance Considerations

1. Four sub-analyzers run sequentially in the hot path (Coverage → Strength → Freshness → Conflict).
2. Coverage Analyzer: O(n×m) where n = clauses, m = evidence chunks — bounded by top_k (≤10).
3. Evidence Strength Scorer: O(k) — linear scan of evidence list.
4. Freshness Analyzer: O(k) — date arithmetic per chunk.
5. Conflict Detector: O(k²) pairs — bounded by `max_conflict_pairs_evaluated` setting (default 20).
6. Total < 50ms for k=10 evidence items (confirmed by performance targets).
7. Optional: run analyzers concurrently (`asyncio.gather`) if each is made async.

---

## 25. Scalability Considerations

1. `ConfidencePolicyStore` uses Redis read-through cache (< 1ms lookup) backed by PostgreSQL.
2. `ConfidenceEngine` is stateless — horizontally scalable.
3. NLI inference (if cloud-based) can be batched using a queue-based worker.
4. `ConfidenceEvaluationLog` write is fire-and-forget (`asyncio.create_task`).

---

## 26. Logging Strategy

```python
logger.info("confidence.evaluation.complete",
    tenant_id=tenant_id,
    correlation_id=correlation_id,
    score=result.score,
    action=result.action.value,
    coverage_score=result.coverage_metrics.overall_coverage_score,
    conflict_score=result.conflict_report.conflict_score,
    has_severe_conflict=result.conflict_report.has_severe_conflict,
    duration_ms=duration_ms
)

logger.warning("confidence.conflict.severe_detected",
    tenant_id=tenant_id,
    correlation_id=correlation_id,
    pair_count=len(severe_pairs)
)
```

---

## 27. Monitoring Strategy

### New Prometheus Metrics (Phase 6)

```
raguard_confidence_score_distribution (histogram, labels: action)
raguard_confidence_action_total (counter, labels: action)
raguard_confidence_coverage_score (histogram)
raguard_confidence_conflict_score (histogram)
raguard_confidence_freshness_score (histogram)
raguard_confidence_strength_score (histogram)
raguard_confidence_severe_conflict_total (counter)
raguard_confidence_evaluation_duration_seconds (histogram)
```

---

## 28. Error Handling Strategy

| Error Code | Exception | HTTP Status | Description |
|---|---|---|---|
| CNF_001 | `InsufficientEvidenceError` | 422 | Empty evidence list |
| CNF_002 | `CoverageAnalyzerError` | 500 | Coverage analysis internal error |
| CNF_003 | `ConflictDetectorError` | 500 | Conflict detection internal error |
| CNF_004 | `PolicyNotFoundError` | 404 | Tenant policy not found (uses default) |
| CNF_005 | `PolicyWeightError` | 400 | Weights don't sum to ~1.0 |

---

## 29. Testing Strategy

### Unit Tests
- `CoverageAnalyzer`: clause extraction, token overlap, semantic coverage, empty query, multi-clause.
- `EvidenceStrengthScorer`: authority scoring, corroboration (1/2/3+ sources), citation density bounds.
- `FreshnessAnalyzer`: linear decay, exponential decay, step decay, future documents (score=1.0), ancient documents (score=0.0).
- `ConflictDetector`: numeric conflict detection, keyword antonym detection, NLI mock, severity grading.
- `ConfidenceEngine`: weight matrix application, threshold routing (all 4 actions), degraded mode thresholds.
- `ConfidencePolicyStore`: get_policy (cache hit/miss), set_policy validation, reset to defaults.

### Integration Tests
- `POST /api/v1/confidence/evaluate` with real evidence data.
- Policy update → evaluate → verify new thresholds applied.
- Severe conflict → forced ABORT regardless of score.
- Degraded retrieval input → elevated thresholds applied.

---

## 30. Unit Testing Plan

| Test Class | Tests |
|---|---|
| `TestCoverageAnalyzerV2` | `test_clause_extraction`, `test_token_overlap`, `test_multi_clause_partial_coverage`, `test_empty_evidence`, `test_full_coverage` |
| `TestEvidenceStrengthScorer` | `test_single_source_low_corroboration`, `test_multi_source_high_corroboration`, `test_authority_metadata_tag`, `test_citation_density_bounded`, `test_rerank_confidence_signal` |
| `TestFreshnessAnalyzerV2` | `test_linear_decay_midpoint`, `test_exponential_decay_halflife`, `test_step_decay_boundaries`, `test_future_document_score_one`, `test_ancient_document_score_zero` |
| `TestConflictDetectorV2` | `test_no_conflict_clean_evidence`, `test_numeric_conflict_detected`, `test_keyword_antonym_detected`, `test_severity_minor_moderate_severe`, `test_severe_forces_abort` |
| `TestConfidenceEngineV2` | `test_proceed_action`, `test_retry_action`, `test_clarify_action`, `test_abort_action`, `test_degraded_mode_thresholds`, `test_custom_weight_matrix` |
| `TestConfidencePolicyStore` | `test_default_policy_returned`, `test_custom_policy_stored`, `test_redis_cache_hit`, `test_postgres_fallback`, `test_invalid_weights_rejected` |

---

## 31. Integration Testing Plan

| Test | Description |
|---|---|
| `test_evaluate_endpoint_proceed` | Full pipeline; expects PROCEED |
| `test_evaluate_endpoint_abort_low_coverage` | Insufficient evidence; expects ABORT |
| `test_evaluate_severe_conflict_forces_abort` | Severe contradiction; expects ABORT |
| `test_policy_update_changes_thresholds` | Admin updates policy; next evaluate uses new thresholds |
| `test_degraded_retrieval_elevates_thresholds` | `is_degraded_fallback=True` input; verify threshold elevation |

---

## 32. Performance Testing Plan

| Scenario | Target | Metric |
|---|---|---|
| Confidence evaluation (k=10) | < 50ms | `raguard_confidence_evaluation_duration_seconds` |
| Policy store cache hit | < 1ms | Redis latency |
| Conflict detection (20 pairs) | < 20ms | OTel span |
| Coverage analysis (5 clauses, k=10) | < 10ms | OTel span |

---

## 33. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| NLI-based conflict detection too slow | Medium | Medium | Default to heuristic provider; NLI optional |
| Policy weight misconfiguration causes wrong routing | Medium | High | Pydantic constraints + weight sum validation |
| Coverage analyzer misses domain-specific clauses | Medium | Medium | Configurable clause splitter patterns per tenant |
| ConfidenceEvaluationLog write failures degrade performance | Low | Low | Fire-and-forget async; failures logged but ignored |
| FreshnessAnalyzer fails on missing document dates | Low | Medium | Default to neutral score (0.5) on missing dates |

---

## 34. Acceptance Criteria

- [ ] Coverage Analyzer correctly identifies uncovered query clauses.
- [ ] Evidence Strength Scorer produces deterministic scores for same input.
- [ ] Freshness Analyzer supports all 3 decay curves; linear is default.
- [ ] Conflict Detector identifies numeric conflicts and keyword antonyms.
- [ ] Severe conflict forces ABORT regardless of aggregate score.
- [ ] Per-tenant `ConfidencePolicy` is applied within < 2ms (Redis cache).
- [ ] All 4 actions (PROCEED / RETRY / CLARIFY / ABORT) tested and reachable.
- [ ] All Phase 6 Prometheus metrics emit correctly.

---

## 35. Completion Criteria

- [ ] All new files created per §17 folder structure.
- [ ] Alembic migration `0010` generated and tested.
- [ ] All unit tests pass (no regressions on existing tests).
- [ ] Integration tests pass.
- [ ] `/api/v1/confidence/evaluate` returns `ConfidenceResultDTOv2`.
- [ ] Git commit: `"Phase 6 Complete: Retrieval Reliability & Confidence Engine"`.
- [ ] Progress tracker updated: 7/23 stages (30.4%).

---

## 36. Milestone Breakdown

### Milestone 6.1 — Schema & Policy Foundation
**Objective**: Extend DTOs; create `ConfidencePolicy` and `ConfidencePolicyStore`.  
**Components**: `confidence_dto.py` extensions, `confidence_policy_store.py`, `confidence_policies` DB table (migration 0010a).  
**Testing**: `TestConfidencePolicyStore` (4 tests).

### Milestone 6.2 — Evidence Strength Scorer
**Objective**: Implement multi-signal evidence quality scorer.  
**Components**: `evidence_strength_scorer.py`.  
**Testing**: `TestEvidenceStrengthScorer` (5 tests).

### Milestone 6.3 — CoverageAnalyzer v2 & FreshnessAnalyzer v2
**Objective**: Productionize existing baseline analyzers with clause extraction and decay curves.  
**Components**: `coverage_analyzer.py` (v2), `freshness_scorer.py` (v2 → renamed `freshness_analyzer.py`).  
**Testing**: `TestCoverageAnalyzerV2` (5 tests), `TestFreshnessAnalyzerV2` (5 tests).

### Milestone 6.4 — Conflict Detector v2
**Objective**: Replace `ContradictionDetector` with production `ConflictDetector` including severity grading.  
**Components**: `conflict_detector.py`, `backend/providers/nli/`.  
**Testing**: `TestConflictDetectorV2` (5 tests).

### Milestone 6.5 — Confidence Engine v2 & REST API
**Objective**: Integrate all analyzers into `ConfidenceEngine` v2; expose REST API.  
**Components**: `confidence_engine.py` (v2), `confidence_log.py`, `confidence_repository.py`, `api/routes.py`, migration 0010.  
**Testing**: `TestConfidenceEngineV2` (6 tests), integration tests (5 tests).

### Milestone 6.6 — Final Integration & Verification
**Objective**: Wire Phase 6 into Phase 5 output; run full regression suite.  
**Testing**: All new + regression tests.  
**Acceptance**: All tests pass; metrics emit; Git commit ready.

---

## 37. Implementation Checklist

- [ ] Extend `backend/modules/confidence/schemas/confidence_dto.py` (v2 DTOs)
- [ ] Create `backend/modules/confidence/services/evidence_strength_scorer.py`
- [ ] Modify `backend/modules/confidence/services/coverage_analyzer.py` (v2)
- [ ] Modify `backend/modules/confidence/services/freshness_scorer.py` (v2 with decay curves)
- [ ] Create `backend/modules/confidence/services/conflict_detector.py`
- [ ] Modify `backend/modules/confidence/services/confidence_engine.py` (v2)
- [ ] Create `backend/modules/confidence/services/confidence_policy_store.py`
- [ ] Create `backend/modules/confidence/models/confidence_log.py`
- [ ] Create `backend/modules/confidence/repositories/confidence_repository.py`
- [ ] Create `backend/modules/confidence/events/payloads.py`
- [ ] Create `backend/modules/confidence/api/routes.py`
- [ ] Create `backend/modules/confidence/api/dependencies.py`
- [ ] Create `backend/providers/nli/__init__.py`
- [ ] Create `backend/providers/nli/base.py`
- [ ] Create `backend/providers/nli/heuristic_provider.py`
- [ ] Register `/api/v1/confidence` router in `backend/api/v1/router.py`
- [ ] Generate Alembic migration `0010_confidence_v2_schema.py`
- [ ] Write unit tests (~30 tests across 6 classes)
- [ ] Write integration tests (~5 tests)
- [ ] Run full regression suite
- [ ] Update `task.md` and `walkthrough.md`

---

## 38. Deliverables

1. Production `ConfidenceEngine` v2 with configurable weight matrix.
2. `CoverageAnalyzer` v2 with clause-level granularity.
3. `EvidenceStrengthScorer` with 4-signal scoring.
4. `FreshnessAnalyzer` v2 with 3 decay curve types.
5. `ConflictDetector` v2 with severity grading.
6. `ConfidencePolicyStore` with Redis caching.
7. `ConfidenceEvaluationLog` ORM + `ConfidenceRepository`.
8. REST API: evaluate + policy management.
9. Alembic migration `0010`.
10. Complete unit + integration test suite.

---

## 39. Phase Completion Checklist

- [ ] All milestones 6.1–6.6 completed and verified.
- [ ] Full backend test suite passes.
- [ ] Frontend production build passes.
- [ ] Alembic migration 0010 applied and verified.
- [ ] Git commit: `"Phase 6 Complete: Retrieval Reliability & Confidence Engine"`.
- [ ] GitHub push to `main`.
- [ ] Progress tracker: 7/23 stages (30.4%).
