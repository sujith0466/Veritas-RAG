# Phase 11 Implementation Plan — Reflection Engine (Production Grade)

**Phase Name:** Phase 11 — Reflection Engine
**Target Module:** `backend/modules/reflection/`
**Status:** Planning & Architecture Baseline (Approved for Future Script-Based Implementation)
**Author:** Veritas RAG Principal Architecture & Enterprise QA Team

---

## 1. Executive Summary

Phase 11 delivers the enterprise **Self-Reflection Engine** (`backend/modules/reflection/`), providing post-generation audit and multi-pass reasoning capabilities before answers are served to end users. Extending the Phase 3 baseline (`ReflectionEngine` and `ClaimValidator`), Phase 11 introduces comprehensive completeness evaluation, logical consistency review, self-reflection workflow orchestration, and structured reflection scoring (`ReflectionScoreDTO`). All components integrate cleanly with `ExecutionGateway` and open-source observability (`OpenTelemetry` and `Prometheus`), ensuring zero-regression compatibility with Wave 1 (`Phases 0–7`) and Wave 2 (`Phases 8–10`).

---

## 2. Phase Objectives

1. **Completeness Evaluation**: Validate that every user query requirement or sub-clause is addressed in the generated answer.
2. **Logical Consistency Review**: Detect internal contradictions and logical fallacies across generated claims and cited excerpts.
3. **Multi-Pass Reasoning**: Enable multi-attempt self-correction loops when initial reflection yields unserved or low-confidence verdicts.
4. **Structured Reflection Scoring**: Produce standardized reflection verdicts (`SUPPORTED`, `UNSUPPORTED`, `CONTRADICTED`, `INCOMPLETE`) with numeric confidence and completeness scores.
5. **Observability & Event Integration**: Emit structured audit events (`ReflectionCompletedEvent`) and record real-time Prometheus metrics (`raguard_reflection_score`).

---

## 3. Business Goals

* **Zero Factual Contradictions**: Eliminate serving contradicted or logically inconsistent answers in high-risk enterprise workflows (legal, medical, finance).
* **Auditability**: Provide transparent post-generation audit trails tracing exactly why a response was deemed safe or unsafe to serve.
* **SLA Compliance**: Maintain sub-300ms overhead for reflection passes within the SLA-bounded execution envelope (`execution_timeout_ms`).

---

## 4. Technical Goals

* **Extend Existing Codebase**: Build directly upon `backend/modules/reflection/services/reflection_engine.py` and `claim_validator.py` without duplication.
* **Async-First Execution**: Execute completeness and logical review passes concurrently using `asyncio.gather`.
* **Clean Architecture Compliance**: Strictly isolate domain logic (`ReflectionEngine`) from infrastructure providers (`LLMProvider`) and API controllers (`routes.py`).

---

## 5. Scope

* Extension of `ReflectionRequestDTO` and `ReflectionResultDTO` (`v2` contracts with backward compatibility aliases).
* Implementation of `CompletenessEvaluator` (`backend/modules/reflection/services/completeness_evaluator.py`).
* Implementation of `LogicalConsistencyReviewer` (`backend/modules/reflection/services/logical_reviewer.py`).
* Extension of `ReflectionEngine` to coordinate multi-pass reflection and scoring.
* REST API endpoints (`POST /reflection/v2/evaluate`, `GET /reflection/v2/history/{correlation_id}`).
* Database migration `0012_reflection_engine_v2.py` for persistent reflection logs.

---

## 6. Out of Scope

* Initial answer generation (governed by Phase 10 `GroundedGenerationService`).
* Final reliability scoring (governed by Phase 13 `ReliabilityScorer`).
* Query rewriting and clarification (governed by Phase 8 and Phase 9).

---

## 7. PRD Alignment

Aligns directly with PRD Section 4.3 (*Answer Self-Correction and Verification*), ensuring every generated answer undergoes multi-dimensional review for logical soundess and completeness before returning to the user or triggering retry flows.

---

## 8. Architecture Alignment

Strictly adheres to `ARCHITECTURE_AFTER_IMPROVEMENTS.md` and `AI_ARCHITECTURE_AFTER_IMPROVEMENTS.md`. It consumes `GroundedAnswerDTO` from Phase 10 and produces `ReflectionResultDTOv2`, which is consumed by `ExecutionGateway` (Phase 3/13) to determine whether to return the payload, trigger a retry (Phase 7), or initiate clarification (Phase 9).

---

## 9. Dependency Analysis

* **Upstream Dependencies**:
  * Phase 10 (`backend/modules/generation/`): Consumes `GroundedAnswerDTO`.
  * Phase 6 (`backend/modules/confidence/`): Consumes `ConfidenceResultDTOv2` for baseline context.
* **Downstream Dependencies**:
  * Phase 13 (`backend/modules/scoring/`): Consumes `ReflectionResultDTOv2` for `ReliabilityScoreEngine`.
  * Phase 7 (`backend/modules/retry/`): Consumes reflection verdicts to inform `DecisionEngine` policies.

---

## 10. Existing Codebase Review

* `backend/modules/reflection/services/claim_validator.py`: Contains `ClaimValidator` checking individual sentence-to-excerpt entailment using `_SENTENCE_PATTERN` and `[N]` citations.
* `backend/modules/reflection/services/reflection_engine.py`: Contains `ReflectionEngine.reflect()` computing `hallucination_score` against `HALLUCINATION_THRESHOLD = 0.3`.
* **Justification for New Components**: Existing code checks sentence citation presence and entailment, but lacks completeness evaluation against the original query clauses and lacks cross-sentence logical consistency verification.

---

## 11. High-Level Architecture

```
ExecutionGateway (Phase 3/13)
        │
        ▼ (GroundedAnswerDTO + Original Query)
┌────────────────────────────────────────────────────────┐
│ ReflectionEngine (Phase 11 Orchestrator)              │
│  ├─► ClaimValidator (Existing Entailment Check)        │
│  ├─► CompletenessEvaluator (Query Clause Coverage)     │
│  └─► LogicalConsistencyReviewer (Internal Contradictions)│
└────────────────────────────────────────────────────────┘
        │
        ▼ (ReflectionResultDTOv2 + ReflectionCompletedEvent)
ExecutionGateway / ReliabilityScorer
```

---

## 12. Low-Level Design

* **Completeness Scoring**: Decomposes original query into requirements $R = \{r_1, r_2, \dots, r_n\}$ and checks if each $r_i$ is addressed by at least one claim. Completeness score $C = \frac{|R_{\text{addressed}}|}{|R|}$.
* **Consistency Review**: Pairwise comparison of generated claims $(c_i, c_j)$ and cited excerpts to detect mutual exclusion or temporal/numerical conflicts.
* **Multi-Pass Loop**: If $C < 0.7$ or `hallucination_score > 0.1` and `attempt < max_reflection_passes`, `ReflectionEngine` flags specific gaps (`unaddressed_clauses`, `contradictory_claims`) for targeted regeneration.

---

## 13. Component Design

1. **`ReflectionEngine`**: Coordinates async evaluations and calculates composite reflection verdicts.
2. **`CompletenessEvaluator`**: Extracts query requirements and verifies coverage.
3. **`LogicalConsistencyReviewer`**: Evaluates claim pairs for logical entailment and consistency.
4. **`ReflectionRepository`**: Persists reflection audit logs to PostgreSQL.

---

## 14. Module Responsibilities

| Module / Class | Responsibility |
| :--- | :--- |
| `schemas/reflection_dto.py` | Defines `ReflectionRequestDTOv2`, `ReflectionScoreDTO`, and `CompletenessReportDTO`. |
| `services/completeness_evaluator.py` | Implements query requirement extraction and coverage scoring. |
| `services/logical_reviewer.py` | Implements contradiction and logical fallacy detection across claims. |
| `services/reflection_engine.py` | Orchestrates multi-pass reflection and emits audit telemetry. |
| `repositories/reflection_repository.py` | ORM operations for saving and querying `ReflectionLogORM`. |

---

## 15. Data Flow

1. `ExecutionGateway` passes `GroundedAnswerDTO` and `original_query` to `ReflectionEngine.reflect_async()`.
2. `ReflectionEngine` calls `ClaimValidator.validate_all()`, `CompletenessEvaluator.evaluate()`, and `LogicalConsistencyReviewer.review()` concurrently via `asyncio.gather`.
3. Scores are synthesized into `ReflectionResultDTOv2`.
4. `ReflectionRepository.save_log()` stores telemetry; `ReflectionCompletedEvent` is published to event bus.

---

## 16. Sequence Diagrams

```
Gateway -> ReflectionEngine: reflect_async(request_v2)
activate ReflectionEngine
ReflectionEngine -> ClaimValidator: validate_claims(answer, citations)
ReflectionEngine -> CompletenessEvaluator: evaluate(original_query, answer_text)
ReflectionEngine -> LogicalReviewer: review(claim_results, citations)
ClaimValidator --> ReflectionEngine: claim_results
CompletenessEvaluator --> ReflectionEngine: completeness_score, unaddressed
LogicalReviewer --> ReflectionEngine: consistency_score, conflicts
ReflectionEngine -> ReflectionRepo: save_log(result_v2)
ReflectionEngine -> EventBus: publish(ReflectionCompletedEvent)
ReflectionEngine --> Gateway: ReflectionResultDTOv2
deactivate ReflectionEngine
```

---

## 17. Folder Structure Changes

```
backend/modules/reflection/
├── __init__.py
├── api/
│   ├── __init__.py
│   └── routes.py              # [NEW] Phase 11 REST endpoints
├── models/
│   ├── __init__.py
│   └── reflection_log.py      # [NEW] SQLAlchemy ORM model
├── repositories/
│   ├── __init__.py
│   └── reflection_repository.py # [NEW] Repository pattern
├── schemas/
│   ├── __init__.py
│   ├── errors.py              # [NEW] Reflection exception hierarchy
│   └── reflection_dto.py      # [MODIFY] Add v2 schemas
└── services/
    ├── __init__.py
    ├── claim_validator.py     # [PRESERVED/EXTENDED]
    ├── completeness_evaluator.py # [NEW]
    ├── logical_reviewer.py    # [NEW]
    └── reflection_engine.py   # [MODIFY] Async v2 orchestration
```

---

## 18. File Creation Plan

| File Path | Type | Justification / Purpose |
| :--- | :--- | :--- |
| `backend/modules/reflection/schemas/errors.py` | New | Defines `ReflectionEvaluationFailed`, `ContradictionDetectedError`. |
| `backend/modules/reflection/schemas/reflection_dto.py` | Modify | Add `ReflectionRequestDTOv2`, `ReflectionResultDTOv2`, `ReflectionScoreDTO`. |
| `backend/modules/reflection/services/completeness_evaluator.py` | New | Implements query clause coverage checking. |
| `backend/modules/reflection/services/logical_reviewer.py` | New | Implements pairwise logical consistency checks. |
| `backend/modules/reflection/services/reflection_engine.py` | Modify | Add async multi-pass orchestration while keeping `reflect()` baseline. |
| `backend/modules/reflection/models/reflection_log.py` | New | ORM model for persistent reflection audit history. |
| `backend/modules/reflection/repositories/reflection_repository.py` | New | Repository for storing/retrieving reflection logs. |
| `backend/modules/reflection/api/routes.py` | New | FastAPI endpoints (`/reflection/v2/*`). |
| `alembic/versions/0012_reflection_engine_v2.py` | New | Database migration table `reflection_logs`. |

---

## 19. Database Changes

### Table: `reflection_logs`
| Column Name | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | UUID | PRIMARY KEY | Unique log record ID |
| `correlation_id` | VARCHAR(128) | NOT NULL, INDEX | Trace tracking ID |
| `tenant_id` | VARCHAR(64) | NOT NULL, INDEX | Tenant namespace |
| `overall_verdict` | VARCHAR(32) | NOT NULL | `SUPPORTED`, `UNSUPPORTED`, `CONTRADICTED` |
| `hallucination_score`| FLOAT | NOT NULL | Ratio of ungrounded claims |
| `completeness_score` | FLOAT | NOT NULL | Ratio of addressed query requirements |
| `consistency_score`  | FLOAT | NOT NULL | Score reflecting internal logical soundess |
| `is_safe_to_serve`   | BOOLEAN | NOT NULL | Final serving gate decision |
| `metadata_payload`   | JSONB | NOT NULL | Full claim breakdown and unaddressed clauses |
| `created_at` | TIMESTAMP | NOT NULL | Record creation timestamp |

---

## 20. API Design

| Method | Endpoint | Request Body | Response DTO | Summary |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/reflection/evaluate` | `ReflectionRequestDTOv2` | `ReflectionResultDTOv2` | Execute multi-pass reflection on grounded answer |
| `GET` | `/api/v1/reflection/history/{correlation_id}` | N/A | `list[ReflectionResultDTOv2]` | Retrieve reflection audit history for a correlation ID |

---

## 21. Configuration Changes

Add to `configs/app_config.py` and `backend/core/config.py`:
* `REFLECTION_MAX_PASSES`: Default `2` (Max self-correction loops).
* `REFLECTION_COMPLETENESS_THRESHOLD`: Default `0.75`.
* `REFLECTION_CONSISTENCY_THRESHOLD`: Default `0.85`.

---

## 22. Environment Variables

| Variable Name | Default | Description |
| :--- | :--- | :--- |
| `RAGUARD_REFLECTION_MAX_PASSES` | `2` | Maximum multi-pass reflection attempts before final decision |
| `RAGUARD_REFLECTION_TIMEOUT_MS` | `350` | Timeout threshold for concurrent reflection evaluation |
| `RAGUARD_REFLECTION_ENABLED` | `true` | Feature flag to enable/disable post-generation reflection |

---

## 23. Security Considerations

* **Tenant Isolation**: Every reflection log query and repository operation MUST filter strictly by `tenant_id`.
* **Sanitization**: Excerpts and claims checked during logical review must undergo `PromptGuard` validation to prevent secondary prompt injection.

---

## 24. Performance Considerations

* **Concurrent Execution**: `ClaimValidator`, `CompletenessEvaluator`, and `LogicalConsistencyReviewer` MUST run asynchronously using `asyncio.gather` to execute within `<= 350ms`.
* **Heuristic Fast-Path**: If `GroundedAnswerDTO.is_fully_grounded == False` and evidence count is `0`, return `UNSUPPORTED` immediately without invoking heavy review logic.

---

## 25. Monitoring Strategy

* **OpenTelemetry Tracing**: Wrap reflection execution inside span `raguard.reflection.evaluate` recording `hallucination_score` and `completeness_score`.
* **Prometheus Metrics**:
  * `raguard_reflection_evaluations_total{verdict, tenant_id}`
  * `raguard_reflection_latency_milliseconds{stage}`
  * `raguard_reflection_hallucination_score_gauge`

---

## 26. Error Handling Strategy

* Raise `ReflectionEvaluationFailed` on unrecoverable timeouts or missing citations.
* If logical review fails due to LLM provider unavailability, log a structural warning, set `consistency_score = 1.0` (degraded mode), and fall back to `ClaimValidator` baseline results.

---

## 27. Testing Strategy

* **Unit Tests**: Test `CompletenessEvaluator` with missing and addressed clauses; test `LogicalConsistencyReviewer` with contradictory claim pairs.
* **Integration Tests**: Verify database persistence of `ReflectionLogORM` and API endpoint contract compliance (`/api/v1/reflection/evaluate`).
* **Regression Tests**: Ensure Phase 3 baseline `ReflectionEngine.reflect(ReflectionRequestDTO)` continues to return exact expected properties.

---

## 28. Unit Testing Plan

* `tests/unit/backend/modules/reflection/test_completeness_evaluator.py`: Verify requirement extraction and ratios.
* `tests/unit/backend/modules/reflection/test_logical_reviewer.py`: Verify contradiction detection between opposing numerical/temporal statements.
* `tests/unit/backend/modules/reflection/test_reflection_engine_v2.py`: Verify `asyncio.gather` orchestration and combined score calculation.

---

## 29. Integration Testing Plan

* `tests/integration/test_reflection_api.py`: Test POST `/api/v1/reflection/evaluate` with full JWT auth and tenant isolation.
* `tests/integration/test_reflection_repository.py`: Verify `reflection_logs` table migrations and ORM queries.

---

## 30. Risk Assessment

| Risk | Likelihood | Impact | Mitigation Strategy |
| :--- | :--- | :--- | :--- |
| Latency spikes exceeding SLA | Medium | High | Enforce strict `asyncio.wait_for(..., timeout=0.35)` across review tasks with deterministic fast-paths. |
| False positive contradictions | Low | Medium | Use calibrated thresholding (`consistency_score < 0.5` triggers `CONTRADICTED`). |

---

## 31. Acceptance Criteria

1. `ReflectionEngine.reflect_async()` returns valid `ReflectionResultDTOv2` containing `completeness_score` and `consistency_score`.
2. Any claim marked `CONTRADICTED` sets `is_safe_to_serve = False` and `overall_verdict = ClaimVerdict.CONTRADICTED`.
3. All reflection evaluations persist cleanly to `reflection_logs` table in PostgreSQL.

---

## 32. Completion Criteria

* All code committed under `backend/modules/reflection/`.
* Migration `0012_reflection_engine_v2.py` applied and verified.
* 100% of Phase 11 unit and integration tests passing alongside all Phase 0–10 tests.

---

## 33. Milestone Breakdown

* **Milestone 1 (`impl_m11_part1.py`)**: DTO extensions (`reflection_dto.py`, `errors.py`) and database migration `0012_reflection_engine_v2.py` + ORM model.
* **Milestone 2 (`impl_m11_part2.py`)**: Implement `CompletenessEvaluator` and `LogicalConsistencyReviewer`.
* **Milestone 3 (`impl_m11_part3.py`)**: Extend `ReflectionEngine` with async multi-pass orchestration and repository saving + REST API routes (`api/routes.py`).
* **Milestone 4 (`impl_m11_tests.py`)**: Comprehensive unit (`test_completeness_evaluator.py`, `test_logical_reviewer.py`) and integration tests.

---

## 34. Provider Abstraction

All LLM or NLI calls made during logical review or completeness checking MUST go through the `backend/modules/reflection/providers/base.py` (`ReflectionReviewProvider` interface), ensuring no hardcoded vendor SDK calls inside domain services.

---

## 35. Architecture Decision Records (ADR)

* **ADR-011-1**: Use concurrent `asyncio.gather` for independent evaluation passes (`entailment`, `completeness`, `consistency`) to ensure sub-350ms execution overhead.
* **ADR-011-2**: Maintain Phase 3 synchronous `reflect()` method as a wrapper around the async engine for full backward compatibility.

---

## 36. Versioning Strategy

All new DTOs use `v2` suffix (`ReflectionRequestDTOv2`, `ReflectionResultDTOv2`). API endpoints reside under `/api/v1/reflection/v2/evaluate` or accept both v1 and v2 payloads via overloaded Pydantic schemas.

---

## 37. Feature Flags

`RAGUARD_REFLECTION_ENABLED`: If set to `false`, `ReflectionEngine.reflect_async()` immediately returns a pass-through `SUPPORTED` verdict (`is_safe_to_serve = True`, `hallucination_score = 0.0`) with zero overhead.

---

## 38. Performance Budgets

* Maximum CPU time per reflection evaluation: `200ms`.
* Maximum total wall-clock latency including async gathering: `350ms`.
* Maximum database log write duration: `15ms` (executed asynchronously via background task where appropriate).

---

## 39. Deployment Architecture

`ReflectionEngine` deploys within the stateless backend application container instances. Database logs are written to the primary transactional PostgreSQL cluster (`alembic` managed).

---

## 40. Failure Recovery Matrix

| Failure Scenario | Detection Mechanism | Recovery Behavior |
| :--- | :--- | :--- |
| NLI / Review Provider Timeout | `asyncio.TimeoutError` | Log structural warning, set `consistency_score = 1.0`, rely on `ClaimValidator` entailment results. |
| PostgreSQL Database Unreachable | ORM `OperationalError` | Emit OpenTelemetry critical alert, return reflection verdict cleanly without failing user request. |

---

## 41. Dependency Graph

```
Phase 10 (GroundedAnswerDTO) ──► Phase 11 (ReflectionEngine) ──► Phase 13 (ReliabilityScoreEngine)
                                       │
                                       ▼
                             PostgreSQL (`reflection_logs`)
```

---

## 42. Rollback Strategy

If Phase 11 introduces regressions, set `RAGUARD_REFLECTION_ENABLED=false` to instantly bypass v2 reflection logic. Database changes (`0012_reflection_engine_v2.py`) can be rolled back cleanly using `alembic downgrade 0011`.

---

## 43. Success Metrics

* **Hallucination Detection Accuracy**: $> 95\%$ benchmark alignment on golden contradiction evaluation sets.
* **False Rejection Rate**: $< 2\%$ of fully grounded, accurate answers flagged as `UNSUPPORTED`.
* **Latency Overhead**: Mean reflection overhead $< 180\text{ms}$.

---

## 44. Traceability Matrix

| Requirement | PRD Reference | Architecture Document | Implementing Class |
| :--- | :--- | :--- | :--- |
| Completeness Audit | Section 4.3 | `AI_ARCHITECTURE_AFTER_IMPROVEMENTS.md` | `CompletenessEvaluator` |
| Contradiction Check | Section 4.3 | `ARCHITECTURE_AFTER_IMPROVEMENTS.md` | `LogicalConsistencyReviewer` |
| Persistent Audit Trail | Section 6.2 | `DATABASE_DESIGN_AFTER_IMPROVEMENTS.md` | `ReflectionRepository` |

---

## 45. Implementation Checklist

- [ ] Create `schemas/errors.py` and update `schemas/reflection_dto.py`.
- [ ] Create `models/reflection_log.py` and `alembic/versions/0012_reflection_engine_v2.py`.
- [ ] Implement `CompletenessEvaluator` and `LogicalConsistencyReviewer`.
- [ ] Extend `ReflectionEngine` with async multi-pass capabilities.
- [ ] Create `api/routes.py` with FastAPI endpoints.

---

## 46. Phase Completion Checklist

- [ ] All 4 implementation milestones (`impl_m11_*.py`) executed successfully.
- [ ] 100% unit and integration tests passing (`test_reflection_*.py`).
- [ ] No Phase 3 baseline unit test regressions.
- [ ] Static analysis (`mypy`, `ruff`) clean with zero errors.

---

## 47. File Inventory

* **Modified Files**:
  * `backend/modules/reflection/schemas/reflection_dto.py`
  * `backend/modules/reflection/services/reflection_engine.py`
* **New Files**:
  * `backend/modules/reflection/schemas/errors.py`
  * `backend/modules/reflection/services/completeness_evaluator.py`
  * `backend/modules/reflection/services/logical_reviewer.py`
  * `backend/modules/reflection/models/__init__.py`
  * `backend/modules/reflection/models/reflection_log.py`
  * `backend/modules/reflection/repositories/__init__.py`
  * `backend/modules/reflection/repositories/reflection_repository.py`
  * `backend/modules/reflection/api/__init__.py`
  * `backend/modules/reflection/api/routes.py`
  * `alembic/versions/0012_reflection_engine_v2.py`
  * `tests/unit/backend/modules/reflection/test_completeness_evaluator.py`
  * `tests/unit/backend/modules/reflection/test_logical_reviewer.py`
  * `tests/unit/backend/modules/reflection/test_reflection_engine_v2.py`

---

## 48. Cross-Phase Consistency Review

Phase 11 guarantees identical terminology (`SUPPORTED`, `UNSUPPORTED`, `CONTRADICTED`, `GroundedAnswerDTO`, `CorrelationId`) across all Wave 1, 2, and 3 documents. Reflection verdicts directly feed Phase 13 (`ReliabilityScoreEngine`) without intermediate data mutation.

---

## 49. Enterprise Design Review Summary

* **SOLID**: Single responsibility strictly enforced (`CompletenessEvaluator` vs `LogicalConsistencyReviewer`).
* **Clean Architecture**: Domain logic completely decoupled from FastAPI routing and SQLAlchemy ORM models via repository boundaries.
* **Async-First**: All evaluations run concurrently to protect enterprise latency SLAs.

---

## 50. Final Deliverables Summary

* **Folder Structure**: Add `api/`, `models/`, and `repositories/` subdirectories to `backend/modules/reflection/`.
* **Database**: Migration `0012_reflection_engine_v2.py` creating `reflection_logs`.
* **API Inventory**: `POST /api/v1/reflection/evaluate`, `GET /api/v1/reflection/history/{correlation_id}`.
* **Milestone Scripts**: `impl_m11_part1.py`, `impl_m11_part2.py`, `impl_m11_part3.py`, `impl_m11_tests.py`.
