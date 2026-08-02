# Phase 12 Implementation Plan — Answer Validation Engine (Production Grade)

**Phase Name:** Phase 12 — Answer Validation
**Target Module:** `backend/modules/validation/`
**Status:** Planning & Architecture Baseline (Approved for Future Script-Based Implementation)
**Author:** RAGuard Principal Architecture & Enterprise QA Team

---

## 1. Executive Summary

Phase 12 delivers the enterprise **Answer Validation Engine** (`backend/modules/validation/`), establishing rigorous grounding verification, natural language inference (NLI) fact alignment, and citation integrity checking. While Phase 10 provides baseline citation formatting and Phase 11 performs reflection review, Phase 12 implements deep claim-level entailment and unsupported claim detection (`FactAlignmentEngine`, `NLIValidationEngine`), guaranteeing that every claim served to the user is explicitly entailed by retrieved evidence. All validation metrics and events feed directly into Phase 13 (`ReliabilityScoreEngine`) and open-source observability (`OpenTelemetry` and `Prometheus`).

---

## 2. Phase Objectives

1. **Claim Extraction**: Isolate atomic factual claims from generated paragraphs and map each claim to exact citation markers (`[1]`, `[2]`).
2. **Citation Integrity & Validation**: Verify that cited document excerpts (`chunk_id`, `document_id`) genuinely exist in the retrieval context and contain exact verbatim support.
3. **Fact Alignment & Unsupported Claim Detection**: Detect claims that hallucinate facts or generalize beyond the scope of retrieved evidence.
4. **Natural Language Inference (NLI) Validation**: Execute deep entailment analysis classifying each claim-excerpt pair into `ENTAILED`, `NEUTRAL`, or `CONTRADICTED`.
5. **Validation APIs & Telemetry**: Provide structured validation verdicts (`ValidationResultDTO`) via REST API (`/api/v1/validation/verify`) and emit validation telemetry.

---

## 3. Business Goals

* **Mathematical Grounding Guarantee**: Ensure enterprise legal, financial, and compliance responses meet rigorous SLA criteria where ungrounded statements are automatically flagged or suppressed.
* **Granular Auditability**: Provide claim-by-claim entailment breakdown reports for compliance officers and AI governance audits.
* **Low-Latency Verification**: Execute high-precision validation passes within `< 300ms` using concurrent NLI evaluation pipelines.

---

## 4. Technical Goals

* **Populate Missing Module Architecture**: Build out `backend/modules/validation/` (which currently contains only an empty `__init__.py`) following clean architecture and domain boundaries.
* **Provider Abstraction**: Enforce `NLIValidationProvider` abstraction (`backend/modules/validation/providers/base.py`) so local cross-encoders (`distilroberta-nli` via ONNX or API) can be swapped seamlessly without domain coupling.
* **Zero Regression**: Preserve 100% compatibility with Phase 10 `GroundedAnswerDTO` and Phase 11 `ReflectionResultDTOv2`.

---

## 5. Scope

* Implementation of schemas (`validation_dto.py`, `errors.py`) inside `backend/modules/validation/schemas/`.
* Implementation of `ClaimExtractor` (`services/claim_extractor.py`).
* Implementation of `CitationIntegrityChecker` (`services/citation_checker.py`).
* Implementation of `NLIValidationEngine` (`services/nli_engine.py`).
* Implementation of `ValidationEngine` orchestrator (`services/validation_engine.py`).
* Provider layer (`providers/base.py`, `providers/cross_encoder_provider.py`).
* REST API routes (`api/routes.py`).
* ORM model (`models/validation_log.py`) and migration `0013_answer_validation_schema.py`.

---

## 6. Out of Scope

* Initial retrieval and reranking (governed by Phase 5).
* Post-generation multi-pass self-reflection loops (governed by Phase 11).
* Final composite reliability score calculation (governed by Phase 13).

---

## 7. PRD Alignment

Aligns directly with PRD Section 4.4 (*Hallucination Prevention and Grounding Verification*), mandating strict entailment verification between generated claims and retrieved source documents before returning answers.

---

## 8. Architecture Alignment

Adheres strictly to `AI_ARCHITECTURE_AFTER_IMPROVEMENTS.md` and `LOW_LEVEL_DESIGN_AFTER_IMPROVEMENTS.md`. It acts as the definitive grounding verification barrier after Phase 10 generation/Phase 11 reflection and prior to Phase 13 final scoring.

---

## 9. Dependency Analysis

* **Upstream Dependencies**:
  * Phase 10 (`backend/modules/generation/`): Consumes `GroundedAnswerDTO` and citation maps.
  * Phase 11 (`backend/modules/reflection/`): Consumes `ReflectionResultDTOv2` when executing chained verification.
* **Downstream Dependencies**:
  * Phase 13 (`backend/modules/scoring/`): Consumes `ValidationResultDTO` (`entailment_ratio`, `unsupported_claim_count`) to compute the overall reliability score.
  * Phase 16 (`backend/modules/dashboard/`): Consumes validation logs to display real-time hallucination rates.

---

## 10. Existing Codebase Review

* `backend/modules/validation/__init__.py`: Currently an empty package (80 bytes).
* **Justification for New Components**: Because `validation/` currently lacks domain logic, we must create the schemas, services, repositories, and APIs from scratch while strictly following the established clean architecture folder conventions seen in `backend/modules/retrieval/` and `backend/modules/confidence/`.

---

## 11. High-Level Architecture

```
GroundedAnswerDTO (Phase 10/11)
        │
        ▼
┌─────────────────────────────────────────────────────────┐
│ ValidationEngine (Phase 12 Orchestrator)               │
│  ├─► ClaimExtractor (Extract atomic factual claims)     │
│  ├─► CitationIntegrityChecker (Verify chunk existence)  │
│  └─► NLIValidationEngine (Cross-encoder entailment)     │
└─────────────────────────────────────────────────────────┘
        │
        ▼ (ValidationResultDTO + ValidationCompletedEvent)
ReliabilityScoreEngine (Phase 13)
```

---

## 12. Low-Level Design

* **Claim Atomic Decomposition**: Extracts declarative sentences from answer text and assigns them unique `claim_id` hashes alongside referenced citation markers $M = \{[1], [2], \dots\}$.
* **Entailment Classification**: For each $(c_i, e_j) \in C \times E$, cross-encoder calculates logits $L = (l_{\text{entail}}, l_{\text{neutral}}, l_{\text{contradict}})$. Entailment ratio is calculated as:
  $$E_{\text{ratio}} = \frac{|\{c_i \in C \mid \text{verdict}(c_i) == \text{ENTAILED}\}|}{|C|}$$
* **Unsupported Thresholding**: If $E_{\text{ratio}} < 0.85$ or if any claim is classified as `CONTRADICTED`, `ValidationEngine` marks `is_grounded = False` and attaches granular claim failure notes.

---

## 13. Component Design

1. **`ValidationEngine`**: Main domain orchestrator executing claim extraction and entailment verification.
2. **`ClaimExtractor`**: NLP sentence splitting and citation token association.
3. **`CitationIntegrityChecker`**: Verifies excerpt match and reference accuracy against retrieved chunks.
4. **`NLIValidationEngine`**: Interfaces with `NLIValidationProvider` to compute entailment logits and classification.

---

## 14. Module Responsibilities

| Module / Class | Responsibility |
| :--- | :--- |
| `schemas/validation_dto.py` | Defines `ValidationRequestDTO`, `ValidationResultDTO`, `ClaimEntailmentDTO`. |
| `services/claim_extractor.py` | Extracts atomic claims and links inline citation markers. |
| `services/citation_checker.py` | Validates verbatim excerpt integrity against source chunk text. |
| `services/nli_engine.py` | Executes NLI entailment classification (`ENTAILED`, `NEUTRAL`, `CONTRADICTED`). |
| `services/validation_engine.py` | Orchestrates the validation pipeline and stores telemetry logs. |

---

## 15. Data Flow

1. `ExecutionGateway` passes `ValidationRequestDTO` (containing `GroundedAnswerDTO`) to `ValidationEngine.validate_async()`.
2. `ClaimExtractor` parses sentences and citations into `ClaimEntailmentDTO` stubs.
3. `CitationIntegrityChecker` verifies that every referenced `[N]` maps to a valid excerpt.
4. `NLIValidationEngine` runs concurrent entailment evaluations against excerpts using `NLIValidationProvider`.
5. `ValidationEngine` aggregates scores into `ValidationResultDTO`, saves `ValidationLogORM`, and publishes `ValidationCompletedEvent`.

---

## 16. Sequence Diagrams

```
Gateway -> ValidationEngine: validate_async(request)
activate ValidationEngine
ValidationEngine -> ClaimExtractor: extract_claims(answer_text)
ValidationEngine -> CitationChecker: verify_integrity(citations, evidence_chunks)
ValidationEngine -> NLIEngine: classify_entailment(claims, citations)
NLIEngine -> NLIProvider: compute_entailment_batch(pairs)
NLIProvider --> NLIEngine: logits / verdicts
NLIEngine --> ValidationEngine: claim_entailment_list
ValidationEngine -> ValidationRepo: save_log(result)
ValidationEngine -> EventBus: publish(ValidationCompletedEvent)
ValidationEngine --> Gateway: ValidationResultDTO
deactivate ValidationEngine
```

---

## 17. Folder Structure Changes

```
backend/modules/validation/
├── __init__.py
├── api/
│   ├── __init__.py
│   └── routes.py                # [NEW] REST endpoints
├── models/
│   ├── __init__.py
│   └── validation_log.py        # [NEW] ORM model
├── providers/
│   ├── __init__.py
│   ├── base.py                  # [NEW] NLI provider abstraction
│   └── cross_encoder_provider.py # [NEW] Cross-encoder implementation
├── repositories/
│   ├── __init__.py
│   └── validation_repository.py # [NEW] Repository layer
├── schemas/
│   ├── __init__.py
│   ├── errors.py                # [NEW] Exception definitions
│   └── validation_dto.py        # [NEW] DTO schemas
└── services/
    ├── __init__.py
    ├── citation_checker.py      # [NEW]
    ├── claim_extractor.py       # [NEW]
    ├── nli_engine.py            # [NEW]
    └── validation_engine.py     # [NEW]
```

---

## 18. File Creation Plan

| File Path | Type | Justification / Purpose |
| :--- | :--- | :--- |
| `backend/modules/validation/schemas/errors.py` | New | Defines `ValidationFailedError`, `BrokenCitationError`. |
| `backend/modules/validation/schemas/validation_dto.py` | New | Defines `ValidationRequestDTO`, `ValidationResultDTO`, `ClaimEntailmentDTO`. |
| `backend/modules/validation/providers/base.py` | New | Abstract base class `NLIValidationProvider`. |
| `backend/modules/validation/providers/cross_encoder_provider.py` | New | Local/Remote cross-encoder NLI provider implementation. |
| `backend/modules/validation/services/claim_extractor.py` | New | Extracts atomic claims and links `[N]` citations. |
| `backend/modules/validation/services/citation_checker.py` | New | Checks citation marker existence and verbatim overlap. |
| `backend/modules/validation/services/nli_engine.py` | New | Manages batch NLI entailment evaluation. |
| `backend/modules/validation/services/validation_engine.py` | New | Domain orchestrator coordinating all validation passes. |
| `backend/modules/validation/models/validation_log.py` | New | ORM entity for persistent validation audit logs. |
| `backend/modules/validation/repositories/validation_repository.py` | New | Repository pattern implementation for `validation_logs`. |
| `backend/modules/validation/api/routes.py` | New | FastAPI routes (`POST /api/v1/validation/verify`). |
| `alembic/versions/0013_answer_validation_schema.py` | New | Alembic migration table `validation_logs`. |

---

## 19. Database Changes

### Table: `validation_logs`
| Column Name | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | UUID | PRIMARY KEY | Unique log ID |
| `correlation_id` | VARCHAR(128) | NOT NULL, INDEX | Trace tracking ID |
| `tenant_id` | VARCHAR(64) | NOT NULL, INDEX | Tenant namespace |
| `entailment_ratio` | FLOAT | NOT NULL | Ratio of `ENTAILED` claims (`0.0 - 1.0`) |
| `unsupported_claims` | INTEGER | NOT NULL | Count of ungrounded or neutral claims |
| `contradicted_claims` | INTEGER | NOT NULL | Count of contradicted claims |
| `is_grounded` | BOOLEAN | NOT NULL | Final grounding verification verdict |
| `claim_breakdown` | JSONB | NOT NULL | Detailed entailment matrix per claim |
| `created_at` | TIMESTAMP | NOT NULL | Record creation timestamp |

---

## 20. API Design

| Method | Endpoint | Request Body | Response DTO | Summary |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/validation/verify` | `ValidationRequestDTO` | `ValidationResultDTO` | Execute full entailment validation on grounded answer |
| `GET` | `/api/v1/validation/logs/{correlation_id}` | N/A | `list[ValidationResultDTO]` | Retrieve validation audit logs for a correlation ID |

---

## 21. Configuration Changes

Add to `configs/app_config.py`:
* `VALIDATION_ENTAILMENT_THRESHOLD`: Default `0.85` (Min required entailment ratio).
* `VALIDATION_NLI_BATCH_SIZE`: Default `16` (Concurrent NLI evaluations).
* `VALIDATION_PROVIDER`: Default `cross_encoder` (`cross_encoder` or `api`).

---

## 22. Environment Variables

| Variable Name | Default | Description |
| :--- | :--- | :--- |
| `RAGUARD_VALIDATION_ENTAILMENT_THRESHOLD` | `0.85` | Minimum entailment ratio to pass validation |
| `RAGUARD_VALIDATION_TIMEOUT_MS` | `300` | Timeout budget for concurrent NLI validation |
| `RAGUARD_VALIDATION_ENABLED` | `true` | Feature flag to enable/disable answer validation |

---

## 23. Security Considerations

* **Tenant Namespace Guard**: All validation queries and logs MUST enforce strict `tenant_id` WHERE clause constraints.
* **Denial of Service Prevention**: Cap maximum claim extractions per answer at `64` to prevent polynomial NLI computation spikes on malformed giant responses.

---

## 24. Performance Considerations

* **Batch NLI Execution**: `NLIValidationEngine` MUST evaluate claim-excerpt pairs in batched tensors or parallel async coroutines (`batch_size=16`) to stay under `300ms`.
* **Zero-Copy Citation Checks**: Use exact substring searching (`in` / fast regex) inside `CitationIntegrityChecker` before triggering heavy NLI models.

---

## 25. Monitoring Strategy

* **OpenTelemetry Tracing**: Record span `raguard.validation.verify` with attributes `claim_count`, `entailment_ratio`, `is_grounded`.
* **Prometheus Metrics**:
  * `raguard_validation_evaluations_total{verdict, tenant_id}`
  * `raguard_validation_latency_milliseconds{stage}`
  * `raguard_validation_entailment_ratio_gauge`

---

## 26. Error Handling Strategy

* Raise `BrokenCitationError` if an inline citation `[N]` references a citation index outside the `evidence_chunks` bounds.
* If NLI inference times out (`asyncio.TimeoutError`), log a structural warning, mark `is_grounded = False`, and return `TIMEOUT_DEGRADED` status cleanly.

---

## 27. Testing Strategy

* **Unit Tests**: Test `ClaimExtractor` sentence boundary detection; test `CitationIntegrityChecker` missing marker detection; mock `NLIValidationProvider` to verify entailment ratio math.
* **Integration Tests**: Verify end-to-end FastAPI endpoint (`/api/v1/validation/verify`) and PostgreSQL `validation_logs` persistence.
* **Regression Tests**: Verify clean interoperation with Phase 10 `GroundedAnswerDTO` structures without altering baseline schema signatures.

---

## 28. Unit Testing Plan

* `tests/unit/backend/modules/validation/test_claim_extractor.py`: Verify atomic sentence separation and `[N]` tag association.
* `tests/unit/backend/modules/validation/test_citation_checker.py`: Test out-of-bounds citation indices and verbatim overlap.
* `tests/unit/backend/modules/validation/test_validation_engine.py`: Test `ValidationEngine.validate_async()` thresholding and score generation.

---

## 29. Integration Testing Plan

* `tests/integration/test_validation_api.py`: Verify POST `/api/v1/validation/verify` responds with `200 OK` and correct `ValidationResultDTO`.
* `tests/integration/test_validation_repository.py`: Verify ORM insertion, index usage, and tenant filtering on `validation_logs`.

---

## 30. Risk Assessment

| Risk | Likelihood | Impact | Mitigation Strategy |
| :--- | :--- | :--- | :--- |
| NLI Cross-Encoder latency high on CPU | Medium | High | Support ONNX runtime acceleration and enforce `VALIDATION_TIMEOUT_MS = 300` fast failovers. |
| NLP sentence splitter misclassifying abbreviations | Medium | Low | Use robust regex boundaries accounting for common abbreviations (`e.g.`, `i.e.`, `Mr.`, `Dr.`). |

---

## 31. Acceptance Criteria

1. `ValidationEngine.validate_async()` returns `is_grounded = True` only when `entailment_ratio >= VALIDATION_ENTAILMENT_THRESHOLD` and `contradicted_claims == 0`.
2. Every claim evaluated includes explicit classification (`ENTAILED`, `NEUTRAL`, `CONTRADICTED`) and supporting excerpt snippets.
3. Validation records persist to `validation_logs` with correct `tenant_id` isolation.

---

## 32. Completion Criteria

* All code committed inside `backend/modules/validation/`.
* Alembic migration `0013_answer_validation_schema.py` applied successfully.
* 100% of Phase 12 unit and integration tests passing without regressions across Phase 0–11.

---

## 33. Milestone Breakdown

* **Milestone 1 (`impl_m12_part1.py`)**: Schemas (`validation_dto.py`, `errors.py`), provider abstraction (`providers/base.py`), and migration `0013_answer_validation_schema.py` + ORM model.
* **Milestone 2 (`impl_m12_part2.py`)**: Implement `ClaimExtractor` and `CitationIntegrityChecker`.
* **Milestone 3 (`impl_m12_part3.py`)**: Implement `NLIValidationEngine`, `ValidationEngine` orchestrator, repository, and REST API (`api/routes.py`).
* **Milestone 4 (`impl_m12_tests.py`)**: Unit and integration test suite execution (`test_validation_engine.py`, `test_claim_extractor.py`).

---

## 34. Provider Abstraction

All entailment calculations MUST implement `NLIValidationProvider` (`backend/modules/validation/providers/base.py`). Concrete implementations (`CrossEncoderProvider`, `APINLIProvider`) are dynamically instantiated based on `app_config.VALIDATION_PROVIDER`.

---

## 35. Architecture Decision Records (ADR)

* **ADR-012-1**: Isolate claim extraction (`ClaimExtractor`) from NLI entailment (`NLIValidationEngine`) to allow independent unit testing and caching of claim structures.
* **ADR-012-2**: Require `entailment_ratio >= 0.85` and `contradictions == 0` for `is_grounded = True`, ensuring strict enterprise compliance.

---

## 36. Versioning Strategy

All schemas inside `validation_dto.py` are versioned as `v1` (`ValidationRequestDTO`, `ValidationResultDTO`) with clear extension point slots for future multi-lingual validation enhancements.

---

## 37. Feature Flags

`RAGUARD_VALIDATION_ENABLED`: When `false`, `ValidationEngine.validate_async()` returns a dummy pass verdict (`is_grounded = True`, `entailment_ratio = 1.0`) with `< 1ms` latency.

---

## 38. Performance Budgets

* Maximum claim extraction duration: `15ms`.
* Maximum batched NLI entailment calculation: `250ms`.
* Total validation engine wall-clock budget: `300ms`.

---

## 39. Deployment Architecture

Deploys inside the main backend container alongside Phase 10/11 services. Cross-encoder models can load into memory or query external inference services via `APINLIProvider`.

---

## 40. Failure Recovery Matrix

| Failure Scenario | Detection Mechanism | Recovery Behavior |
| :--- | :--- | :--- |
| NLI Model Out of Memory / Crash | `RuntimeError` / `TimeoutError` | Log error, emit OpenTelemetry alarm, return `is_grounded = False` with `status = DEGRADED`. |
| Database Log Write Timeout | `asyncio.TimeoutError` on DB pool | Queue log to background Celery worker (`record_validation_audit_task`) without blocking response. |

---

## 41. Dependency Graph

```
Phase 10 (GroundedAnswerDTO) ──► Phase 12 (ValidationEngine) ──► Phase 13 (ReliabilityScoreEngine)
                                       │
                                       ▼
                             PostgreSQL (`validation_logs`)
```

---

## 42. Rollback Strategy

Disable feature flag `RAGUARD_VALIDATION_ENABLED=false` to bypass validation instantly. If database migration `0013` causes issues, run `alembic downgrade 0012`.

---

## 43. Success Metrics

* **Entailment Accuracy**: $> 93\%$ agreement with human-annotated entailment datasets (`ANLI` / `SummEval`).
* **Hallucination Capture Rate**: $> 96\%$ of ungrounded statements flagged correctly.
* **Latency Overhead**: Mean execution latency $< 160\text{ms}$.

---

## 44. Traceability Matrix

| Requirement | PRD Reference | Architecture Document | Implementing Class |
| :--- | :--- | :--- | :--- |
| Claim Entailment Audit | Section 4.4 | `AI_ARCHITECTURE_AFTER_IMPROVEMENTS.md` | `NLIValidationEngine` |
| Citation Marker Check | Section 4.4 | `LOW_LEVEL_DESIGN_AFTER_IMPROVEMENTS.md` | `CitationIntegrityChecker` |
| Validation Telemetry | Section 6.2 | `API_DESIGN_AFTER_IMPROVEMENTS.md` | `ValidationRepository` |

---

## 45. Implementation Checklist

- [ ] Create `schemas/errors.py` and `schemas/validation_dto.py`.
- [ ] Create `providers/base.py` and `providers/cross_encoder_provider.py`.
- [ ] Create `services/claim_extractor.py` and `services/citation_checker.py`.
- [ ] Create `services/nli_engine.py` and `services/validation_engine.py`.
- [ ] Create `models/validation_log.py`, `repositories/validation_repository.py`, and `api/routes.py`.
- [ ] Create migration `0013_answer_validation_schema.py`.

---

## 46. Phase Completion Checklist

- [ ] All 4 implementation scripts (`impl_m12_*.py`) executed cleanly.
- [ ] 100% of Phase 12 unit and integration tests passing (`test_validation_*.py`).
- [ ] Zero static analysis errors (`mypy`, `ruff`).
- [ ] Complete compatibility verified with Phase 10/11 contracts.

---

## 47. File Inventory

* **New Files**:
  * `backend/modules/validation/schemas/__init__.py`
  * `backend/modules/validation/schemas/errors.py`
  * `backend/modules/validation/schemas/validation_dto.py`
  * `backend/modules/validation/providers/__init__.py`
  * `backend/modules/validation/providers/base.py`
  * `backend/modules/validation/providers/cross_encoder_provider.py`
  * `backend/modules/validation/services/__init__.py`
  * `backend/modules/validation/services/claim_extractor.py`
  * `backend/modules/validation/services/citation_checker.py`
  * `backend/modules/validation/services/nli_engine.py`
  * `backend/modules/validation/services/validation_engine.py`
  * `backend/modules/validation/models/__init__.py`
  * `backend/modules/validation/models/validation_log.py`
  * `backend/modules/validation/repositories/__init__.py`
  * `backend/modules/validation/repositories/validation_repository.py`
  * `backend/modules/validation/api/__init__.py`
  * `backend/modules/validation/api/routes.py`
  * `alembic/versions/0013_answer_validation_schema.py`
  * `tests/unit/backend/modules/validation/test_claim_extractor.py`
  * `tests/unit/backend/modules/validation/test_citation_checker.py`
  * `tests/unit/backend/modules/validation/test_validation_engine.py`
  * `tests/integration/test_validation_api.py`

---

## 48. Cross-Phase Consistency Review

Phase 12 uses identical `correlation_id` and `tenant_id` fields, consuming `GroundedAnswerDTO` and producing `ValidationResultDTO` (`entailment_ratio`, `unsupported_claims`) which directly maps to Phase 13's `ValidationScore` input without schema friction.

---

## 49. Enterprise Design Review Summary

* **SOLID**: Single responsibility strictly decoupled (`ClaimExtractor` splits sentences; `NLIValidationEngine` runs tensor inference).
* **Dependency Inversion**: High-level orchestrators depend only on `NLIValidationProvider` abstractions.
* **Async-First**: Batch cross-encoder checks execute inside asynchronous thread pools (`asyncio.to_thread` / `gather`) protecting main event loop responsiveness.

---

## 50. Final Deliverables Summary

* **Folder Structure**: Build out `api/`, `models/`, `providers/`, `repositories/`, `schemas/`, `services/` inside `backend/modules/validation/`.
* **Database**: Migration `0013_answer_validation_schema.py` creating `validation_logs`.
* **API Inventory**: `POST /api/v1/validation/verify`, `GET /api/v1/validation/logs/{correlation_id}`.
* **Milestone Scripts**: `impl_m12_part1.py`, `impl_m12_part2.py`, `impl_m12_part3.py`, `impl_m12_tests.py`.
