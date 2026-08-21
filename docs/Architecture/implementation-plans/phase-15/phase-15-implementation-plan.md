# Phase 15 Implementation Plan — Evaluation & Continuous Learning Engine (Production Grade)

**Phase Name:** Phase 15 — Evaluation & Continuous Learning Engine
**Target Module:** `backend/modules/evaluation/`
**Status:** Planning & Architecture Baseline (Approved for Future Script-Based Implementation)
**Author:** Veritas RAG Principal Architecture & Enterprise QA Team

---

## 1. Executive Summary

Phase 15 delivers the enterprise **Evaluation & Continuous Learning Engine** (`backend/modules/evaluation/`), establishing automated quality benchmarking, golden test dataset curation, and real-time score calibration. Populating the currently empty `backend/modules/evaluation/` domain package, Phase 15 implements standard RAG metric frameworks (RAGAS and TruLens feedback functions) via clean provider abstractions (`RagasProvider`, `TruLensProvider`). It provides continuous evaluation runners that periodically benchmark Phase 5 retrieval and Phase 10/11/12 generation against human-annotated golden datasets (`golden_datasets`), ensuring that Phase 13 reliability scores remain statistically calibrated against ground-truth human evaluations over time.

---

## 2. Phase Objectives

1. **RAGAS & TruLens Integration**: Compute industry-standard RAG evaluation metrics (`faithfulness`, `answer_relevance`, `context_precision`, `context_recall`, `groundedness`) via abstracted evaluation providers.
2. **Golden Dataset Management**: Provide full CRUD curation and versioning for golden test cases (`GoldenItemORM`, `GoldenDatasetORM`).
3. **Continuous Benchmarking Pipelines**: Schedule background evaluation jobs (`ContinuousEvalRunner`) to run automated regression sweeps across golden datasets after system upgrades.
4. **Score Calibration**: Automatically correlate Phase 13 (`ReliabilityScoreEngine`) output scores against human golden ratings to calculate calibration drift ($R^2$ / Spearman correlation).
5. **Observability & REST APIs**: Expose management endpoints (`/api/v1/evaluation/*`) and emit structured evaluation events (`EvaluationBenchmarkCompletedEvent`).

---

## 3. Business Goals

* **Statistical Quality Assurance**: Provide quantitative verification to enterprise stakeholders that model upgrades or prompt changes improve retrieval precision and generation faithfulness.
* **SLA Drift Prevention**: Detect early signs of model degradation or prompt drift before they impact production users.
* **Auditable Governance**: Store comprehensive historical benchmark scores and golden datasets in PostgreSQL (`alembic` migration `0016`).

---

## 4. Technical Goals

* **Populate Missing Module Structure**: Build out `backend/modules/evaluation/` cleanly adhering to domain, provider, service, and repository layers without coupling to vendor SDKs.
* **Provider Abstraction**: Enforce `EvaluationMetricProvider` (`backend/modules/evaluation/providers/base.py`) to allow seamless switching or combining of RAGAS, TruLens, or local custom metric evaluation backends.
* **Async & Background Execution**: Execute long-running benchmark campaigns asynchronously via Celery worker pools to avoid blocking API threads.

---

## 5. Scope

* Implementation of schemas inside `backend/modules/evaluation/schemas/` (`evaluation_dto.py`, `errors.py`).
* Implementation of golden dataset managers (`services/golden_manager.py`).
* Implementation of evaluation runners (`services/eval_runner.py`).
* Implementation of score calibration engine (`services/calibration_engine.py`).
* Provider layer (`providers/base.py`, `providers/ragas_provider.py`, `providers/trulens_provider.py`).
* REST API endpoints (`api/routes.py`).
* ORM models (`models/golden_item.py`, `models/eval_job.py`) and migration `alembic/versions/0016_evaluation_engine_schema.py`.

---

## 6. Out of Scope

* Real-time synchronous serving validation (governed by Phase 12 `ValidationEngine`).
* Production alert dispatching via Slack/PagerDuty (governed by Phase 18).
* Initial chunking and embedding pipeline construction (governed by Phase 1).

---

## 7. PRD Alignment

Aligns directly with PRD Section 6.1 (*Evaluation Framework and Golden Benchmarking*), mandating automated regression testing and statistical evaluation across curated QA pairs.

---

## 8. Architecture Alignment

Strictly adheres to `AI_ARCHITECTURE_AFTER_IMPROVEMENTS.md` and `EVALUATION_FRAMEWORK_AFTER_IMPROVEMENTS.md`. It acts as the offline and background quality assurance authority validating all live pipeline phases.

---

## 9. Dependency Analysis

* **Upstream Dependencies**:
  * Phase 5 (`retrieval`): Evaluated for `context_precision` and `context_recall`.
  * Phase 10 (`generation`): Evaluated for `answer_relevance` and `faithfulness`.
  * Phase 13 (`scoring`): Evaluated for score calibration and alignment against human ratings.
* **Downstream Dependencies**:
  * Phase 16 (`dashboard`): Displays historical evaluation trends and golden dataset accuracy charts.
  * Phase 19 (`analytics`): Ingests benchmark logs for multi-month trend forecasting.

---

## 10. Existing Codebase Review

* `backend/modules/evaluation/__init__.py`: Currently an empty package stub (94 bytes).
* **Justification for New Components**: Because `evaluation/` is currently empty, we must create the schemas, providers, domain services, repositories, ORM entities, and REST controllers from scratch following Veritas RAG architectural standards.

---

## 11. High-Level Architecture

```
Golden Dataset (`golden_items`)
               │
               ▼
┌──────────────────────────────────────────────────────────────┐
│ ContinuousEvalRunner (Phase 15 Orchestrator)                │
│  ├─► RagasProvider (Faithfulness, Precision, Recall)         │
│  ├─► TruLensProvider (Groundedness, Relevance Triad)         │
│  └─► ScoreCalibrationEngine (Correlate with Phase 13 scores) │
└──────────────────────────────────────────────────────────────┘
               │
               ▼
   EvaluationJobORM (`evaluation_jobs`) + `EvaluationSummaryDTO`
```

---

## 12. Low-Level Design

### RAGAS & TruLens Metric Definitions
For a query $Q$, retrieved context $C$, generated answer $A$, and golden reference $G$:
* **Faithfulness**: Proportion of statements in $A$ entailed by $C$.
* **Context Precision**: Signal-to-noise ratio ranking relevant chunks higher in $C$.
* **Context Recall**: Extent to which $C$ covers all information required to reconstruct $G$.
* **Answer Relevance**: Semantic alignment between $A$ and $Q$.

### Calibration Error ($E_{\text{cal}}$)
Let $R_i \in [0, 1]$ be Phase 13 composite reliability score and $H_i \in [0, 1]$ be human/golden ground-truth score:
$$E_{\text{cal}} = \sqrt{\frac{1}{N} \sum_{i=1}^N (R_i - H_i)^2}$$
If $E_{\text{cal}} > 0.15$, `ScoreCalibrationEngine` raises a `CalibrationDriftAlert` to trigger weight retuning in `configs/app_config.py`.

---

## 13. Component Design

1. **`ContinuousEvalRunner`**: Manages execution of benchmark campaigns across dataset items.
2. **`GoldenDatasetManager`**: Handles creation, curation, and import/export of golden QA datasets.
3. **`ScoreCalibrationEngine`**: Computes root-mean-square calibration error and statistical correlation.
4. **`EvaluationRepository`**: Persists benchmark jobs, item results, and golden datasets.

---

## 14. Module Responsibilities

| Module / Class | Responsibility |
| :--- | :--- |
| `schemas/evaluation_dto.py` | Defines `GoldenItemDTO`, `EvaluationRequestDTO`, `EvaluationSummaryDTO`, `CalibrationReportDTO`. |
| `services/golden_manager.py` | CRUD operations and CSV/JSON export/import for golden test cases. |
| `services/eval_runner.py` | Orchestrates batch execution across evaluation providers. |
| `services/calibration_engine.py` | Calculates calibration errors between Phase 13 scores and golden labels. |
| `repositories/eval_repository.py` | Repository layer for `golden_items` and `evaluation_jobs`. |

---

## 15. Data Flow

1. Admin or cron triggers `ContinuousEvalRunner.run_benchmark_async(dataset_id)`.
2. `EvaluationRepository` loads golden items $(Q_i, G_i)$.
3. For each item, pipeline executes retrieval/generation ($C_i, A_i$).
4. `RagasProvider` and `TruLensProvider` compute metric scores.
5. `ScoreCalibrationEngine` compares Phase 13 score against $G_i$.
6. Results persist to `evaluation_jobs`; `EvaluationBenchmarkCompletedEvent` is emitted.

---

## 16. Sequence Diagrams

```
Admin -> EvalRunner: run_benchmark_async(dataset_id)
activate EvalRunner
EvalRunner -> EvalRepo: fetch_golden_items(dataset_id)
EvalRepo --> EvalRunner: golden_items_list
EvalRunner -> ExecutionGateway: run_pipeline_batch(queries)
ExecutionGateway --> EvalRunner: pipeline_results (C, A, R_score)
EvalRunner -> RagasProvider: evaluate_batch(golden_items, pipeline_results)
EvalRunner -> TruLensProvider: evaluate_batch(golden_items, pipeline_results)
RagasProvider --> EvalRunner: ragas_metrics
TruLensProvider --> EvalRunner: trulens_metrics
EvalRunner -> CalibrationEngine: compute_calibration(pipeline_results, golden_items)
CalibrationEngine --> EvalRunner: calibration_report
EvalRunner -> EvalRepo: save_evaluation_job(summary_dto)
EvalRunner -> EventBus: publish(EvaluationBenchmarkCompletedEvent)
EvalRunner --> Admin: EvaluationSummaryDTO
deactivate EvalRunner
```

---

## 17. Folder Structure Changes

```
backend/modules/evaluation/
├── __init__.py
├── api/
│   ├── __init__.py
│   └── routes.py                 # [NEW] REST endpoints
├── models/
│   ├── __init__.py
│   ├── eval_job.py               # [NEW] ORM for eval history
│   └── golden_item.py            # [NEW] ORM for golden datasets
├── providers/
│   ├── __init__.py
│   ├── base.py                   # [NEW] Provider abstraction
│   ├── ragas_provider.py         # [NEW] RAGAS implementation
│   └── trulens_provider.py       # [NEW] TruLens implementation
├── repositories/
│   ├── __init__.py
│   └── eval_repository.py        # [NEW] Repository layer
├── schemas/
│   ├── __init__.py
│   ├── errors.py                 # [NEW] Evaluation exceptions
│   └── evaluation_dto.py         # [NEW] DTO schemas
└── services/
    ├── __init__.py
    ├── calibration_engine.py     # [NEW]
    ├── eval_runner.py            # [NEW]
    └── golden_manager.py         # [NEW]
```

---

## 18. File Creation Plan

| File Path | Type | Justification / Purpose |
| :--- | :--- | :--- |
| `backend/modules/evaluation/schemas/errors.py` | New | Defines `DatasetNotFoundError`, `EvaluationTimeoutError`. |
| `backend/modules/evaluation/schemas/evaluation_dto.py` | New | Defines all golden dataset, job, and metric DTOs. |
| `backend/modules/evaluation/providers/base.py` | New | Abstract base class `EvaluationMetricProvider`. |
| `backend/modules/evaluation/providers/ragas_provider.py` | New | RAGAS metrics wrapper. |
| `backend/modules/evaluation/providers/trulens_provider.py` | New | TruLens feedback functions wrapper. |
| `backend/modules/evaluation/services/golden_manager.py` | New | Curation service for golden datasets. |
| `backend/modules/evaluation/services/eval_runner.py` | New | Continuous evaluation job execution engine. |
| `backend/modules/evaluation/services/calibration_engine.py` | New | Score calibration and correlation analyzer. |
| `backend/modules/evaluation/models/golden_item.py` | New | ORM entity `GoldenItemORM` & `GoldenDatasetORM`. |
| `backend/modules/evaluation/models/eval_job.py` | New | ORM entity `EvaluationJobORM`. |
| `backend/modules/evaluation/repositories/eval_repository.py` | New | Repository for datasets and jobs. |
| `backend/modules/evaluation/api/routes.py` | New | FastAPI endpoints (`/api/v1/evaluation/*`). |
| `alembic/versions/0016_evaluation_engine_schema.py` | New | Alembic migration creating tables. |

---

## 19. Database Changes

### Table: `golden_datasets` & `golden_items`
| Table | Column Name | Type | Constraints | Description |
| :--- | :--- | :--- | :--- | :--- |
| `golden_datasets` | `id` | UUID | PRIMARY KEY | Dataset ID |
| `golden_datasets` | `tenant_id` | VARCHAR(64) | NOT NULL, INDEX | Tenant namespace |
| `golden_datasets` | `name` | VARCHAR(128) | NOT NULL | Dataset title |
| `golden_items` | `id` | UUID | PRIMARY KEY | Item ID |
| `golden_items` | `dataset_id` | UUID | FOREIGN KEY | Parent dataset |
| `golden_items` | `query` | TEXT | NOT NULL | Test question |
| `golden_items` | `reference_answer`| TEXT | NOT NULL | Human ground truth |
| `golden_items` | `expected_chunks` | JSONB | NOT NULL | List of required chunk IDs |

### Table: `evaluation_jobs`
| Column Name | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | UUID | PRIMARY KEY | Job run ID |
| `dataset_id` | UUID | FOREIGN KEY | Benchmarked dataset |
| `tenant_id` | VARCHAR(64) | NOT NULL, INDEX | Tenant namespace |
| `status` | VARCHAR(32) | NOT NULL | `PROCESSING`, `COMPLETED`, `FAILED` |
| `metrics_payload` | JSONB | NOT NULL | Aggregate RAGAS/TruLens scores |
| `calibration_score`| FLOAT | NOT NULL | RMSE calibration error against ground truth |
| `created_at` | TIMESTAMP | NOT NULL | Execution timestamp |

---

## 20. API Design

| Method | Endpoint | Request Body | Response DTO | Summary |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/evaluation/datasets` | `CreateDatasetRequestDTO` | `GoldenDatasetDTO` | Create a new golden benchmarking dataset |
| `POST` | `/api/v1/evaluation/datasets/{id}/items` | `GoldenItemCreateDTO` | `GoldenItemDTO` | Add a golden QA pair to a dataset |
| `POST` | `/api/v1/evaluation/jobs/run` | `RunEvaluationRequestDTO` | `EvaluationJobDTO` | Trigger an async benchmark evaluation campaign |
| `GET` | `/api/v1/evaluation/jobs/{job_id}` | N/A | `EvaluationSummaryDTO` | Retrieve detailed metrics and calibration report |

---

## 21. Configuration Changes

Add to `configs/app_config.py`:
* `EVAL_BATCH_SIZE`: Default `10`.
* `EVAL_DEFAULT_PROVIDER`: Default `"ragas"`.
* `EVAL_MAX_TIMEOUT_MINUTES`: Default `30`.

---

## 22. Environment Variables

| Variable Name | Default | Description |
| :--- | :--- | :--- |
| `RAGUARD_EVAL_DEFAULT_PROVIDER` | `ragas` | Default provider (`ragas`, `trulens`, or `hybrid`) |
| `RAGUARD_EVAL_TIMEOUT_SEC` | `1800` | Timeout threshold for batch evaluation jobs |
| `RAGUARD_EVAL_ENABLED` | `true` | Feature flag enabling evaluation framework |

---

## 23. Security Considerations

* **Tenant Isolation**: Golden datasets and evaluation job logs MUST strictly filter queries by `tenant_id`.
* **Prompt Injection Defense**: Reference answers and queries imported via CSV/JSON must undergo input validation before storage or evaluation execution.

---

## 24. Performance Considerations

* **Asynchronous Execution**: Benchmark evaluations over $> 50$ items MUST run via background Celery tasks (`run_evaluation_task`) returning `status = PROCESSING` immediately to the API caller.
* **Batch LLM Evaluation**: Group evaluation prompts (`batch_size=10`) to optimize provider inference throughput.

---

## 25. Monitoring Strategy

* **OpenTelemetry Tracing**: Record span `raguard.evaluation.benchmark` with attributes `dataset_id`, `faithfulness_avg`, `calibration_rmse`.
* **Prometheus Metrics**:
  * `raguard_eval_faithfulness_gauge{tenant_id}`
  * `raguard_eval_context_precision_gauge{tenant_id}`
  * `raguard_eval_calibration_rmse_gauge{tenant_id}`

---

## 26. Error Handling Strategy

* Raise `DatasetNotFoundError` when attempting to benchmark non-existent datasets.
* If provider inference fails for an item during a batch run, log warning, record `score = None` for that item, and continue processing remaining items without failing the overall job.

---

## 27. Testing Strategy

* **Unit Tests**: Verify mathematical formulas inside `ScoreCalibrationEngine`; mock `EvaluationMetricProvider` to test `ContinuousEvalRunner` aggregation math.
* **Integration Tests**: Verify CRUD endpoints under `/api/v1/evaluation/*` and database migration `0016_evaluation_engine_schema.py`.
* **Regression Tests**: Verify clean interoperation with Phase 13 `ReliabilityScoreEngine` output formats.

---

## 28. Unit Testing Plan

* `tests/unit/backend/modules/evaluation/test_calibration_engine.py`: Test RMSE and Spearman rank correlation computation.
* `tests/unit/backend/modules/evaluation/test_eval_runner.py`: Verify batching and metric aggregation.
* `tests/unit/backend/modules/evaluation/test_golden_manager.py`: Test CSV/JSON dataset import parsing and validation.

---

## 29. Integration Testing Plan

* `tests/integration/test_evaluation_api.py`: Verify authentication, tenant isolation, and async job trigger responses (`202 Accepted`).
* `tests/integration/test_evaluation_repository.py`: Verify ORM insertion and foreign key constraints across `golden_datasets`, `golden_items`, and `evaluation_jobs`.

---

## 30. Risk Assessment

| Risk | Likelihood | Impact | Mitigation Strategy |
| :--- | :--- | :--- | :--- |
| LLM API rate limits triggered during large benchmarks | High | Medium | Implement exponential backoff (`tenacity`) and configurable batch sizes inside `RagasProvider`. |
| Human ground truth subjectivity causing high calibration RMSE | Medium | Low | Enforce multi-annotator averaging and statistical outlier rejection when importing golden items. |

---

## 31. Acceptance Criteria

1. `ContinuousEvalRunner.run_benchmark_async()` calculates and persists exact RAGAS and TruLens metrics for all golden items.
2. `ScoreCalibrationEngine` outputs accurate RMSE error scores comparing Phase 13 reliability ratings against human reference scores.
3. All golden dataset items and evaluation job logs persist cleanly to PostgreSQL with tenant isolation.

---

## 32. Completion Criteria

* All code committed inside `backend/modules/evaluation/`.
* Alembic migration `0016_evaluation_engine_schema.py` applied.
* 100% of Phase 15 unit and integration tests passing alongside all Phase 0–14 tests.

---

## 33. Milestone Breakdown

* **Milestone 1 (`impl_m15_part1.py`)**: Schemas (`evaluation_dto.py`), provider abstraction (`providers/base.py`), and migration `0016_evaluation_engine_schema.py` + ORM models.
* **Milestone 2 (`impl_m15_part2.py`)**: Implement `RagasProvider`, `TruLensProvider`, and `GoldenDatasetManager`.
* **Milestone 3 (`impl_m15_part3.py`)**: Implement `ScoreCalibrationEngine`, `ContinuousEvalRunner`, repository, and REST API (`api/routes.py`).
* **Milestone 4 (`impl_m15_tests.py`)**: Execute unit (`test_calibration_engine.py`, `test_eval_runner.py`) and integration tests.

---

## 34. Provider Abstraction

All evaluation metrics MUST implement `EvaluationMetricProvider` (`backend/modules/evaluation/providers/base.py`), allowing seamless substitution between `RagasProvider`, `TruLensProvider`, or in-house models.

---

## 35. Architecture Decision Records (ADR)

* **ADR-015-1**: Separate online serving validation (`ValidationEngine` Phase 12) from offline/background benchmarking (`ContinuousEvalRunner` Phase 15) to maintain sub-300ms live API SLAs while enabling thorough multi-metric offline sweeps.
* **ADR-015-2**: Store golden test cases (`golden_items`) inside relational PostgreSQL rather than flat files to enable tenant isolation, SQL joins with query logs, and granular versioning.

---

## 36. Versioning Strategy

All schemas use API `v1` contracts (`GoldenDatasetDTO`, `EvaluationJobDTO`), while golden datasets support explicit semantic version tags (`version = "1.2.0"` column on `golden_datasets`).

---

## 37. Feature Flags

`RAGUARD_EVAL_ENABLED`: If `false`, evaluation API endpoints return `503 Service Unavailable (Feature Disabled)` and background cron schedules pause.

---

## 38. Performance Budgets

* Golden item CRUD duration: `10ms`.
* RMSE calibration computation across 1,000 items: `50ms`.
* Async job enqueue overhead: `15ms`.

---

## 39. Deployment Architecture

`ContinuousEvalRunner` tasks execute inside dedicated Celery background workers (`celery worker -Q evaluation`), preventing CPU-intensive metric calculations from impacting live API servers.

---

## 40. Failure Recovery Matrix

| Failure Scenario | Detection Mechanism | Recovery Behavior |
| :--- | :--- | :--- |
| External Eval LLM Provider Error | `OpenAIError` / `HTTPError` | Retry 3 times with exponential backoff; if still failing, mark item `status = ERROR` and continue batch. |
| Database Connection Loss During Save | `OperationalError` | Roll back transaction, log error to OpenTelemetry, retry save via Celery task retry hook. |

---

## 41. Dependency Graph

```
Phases 5, 10, 13 ──► Phase 15 (Evaluation & Continuous Learning Engine) ──► Phase 16 (Dashboard)
                                       │
                                       ▼
                  PostgreSQL (`golden_items`, `evaluation_jobs`)
```

---

## 42. Rollback Strategy

Set `RAGUARD_EVAL_ENABLED=false` to pause evaluation jobs. Run `alembic downgrade 0015` to remove evaluation and golden tables cleanly.

---

## 43. Success Metrics

* **Benchmark Accuracy**: $> 95\%$ correlation between `RagasProvider` faithfulness scores and human expert ratings.
* **Calibration Stability**: System-wide reliability calibration RMSE maintained $< 0.10$.
* **Job Execution Reliability**: $> 99.5\%$ of scheduled evaluation campaigns complete without worker crashes.

---

## 44. Traceability Matrix

| Requirement | PRD Reference | Architecture Document | Implementing Class |
| :--- | :--- | :--- | :--- |
| RAGAS/TruLens Integration | Section 6.1 | `AI_ARCHITECTURE_AFTER_IMPROVEMENTS.md` | `RagasProvider`, `TruLensProvider` |
| Golden Dataset Curation | Section 6.1 | `DATABASE_DESIGN_AFTER_IMPROVEMENTS.md` | `GoldenDatasetManager` |
| Continuous Benchmarking | Section 6.1 | `ARCHITECTURE_AFTER_IMPROVEMENTS.md` | `ContinuousEvalRunner` |

---

## 45. Implementation Checklist

- [ ] Create `schemas/errors.py` and `schemas/evaluation_dto.py`.
- [ ] Create `providers/base.py`, `providers/ragas_provider.py`, and `providers/trulens_provider.py`.
- [ ] Create `services/golden_manager.py`, `services/eval_runner.py`, and `services/calibration_engine.py`.
- [ ] Create `models/golden_item.py`, `models/eval_job.py`, `repositories/eval_repository.py`, and `api/routes.py`.
- [ ] Create migration `0016_evaluation_engine_schema.py`.

---

## 46. Phase Completion Checklist

- [ ] All 4 implementation milestones (`impl_m15_*.py`) executed cleanly.
- [ ] 100% of Phase 15 unit and integration tests passing (`test_eval_*.py`).
- [ ] Zero static analysis errors (`mypy`, `ruff`).
- [ ] No regressions across Phase 0–14 test suites.

---

## 47. File Inventory

* **New Files**:
  * `backend/modules/evaluation/schemas/__init__.py`
  * `backend/modules/evaluation/schemas/errors.py`
  * `backend/modules/evaluation/schemas/evaluation_dto.py`
  * `backend/modules/evaluation/providers/__init__.py`
  * `backend/modules/evaluation/providers/base.py`
  * `backend/modules/evaluation/providers/ragas_provider.py`
  * `backend/modules/evaluation/providers/trulens_provider.py`
  * `backend/modules/evaluation/services/__init__.py`
  * `backend/modules/evaluation/services/golden_manager.py`
  * `backend/modules/evaluation/services/eval_runner.py`
  * `backend/modules/evaluation/services/calibration_engine.py`
  * `backend/modules/evaluation/models/__init__.py`
  * `backend/modules/evaluation/models/golden_item.py`
  * `backend/modules/evaluation/models/eval_job.py`
  * `backend/modules/evaluation/repositories/__init__.py`
  * `backend/modules/evaluation/repositories/eval_repository.py`
  * `backend/modules/evaluation/api/__init__.py`
  * `backend/modules/evaluation/api/routes.py`
  * `alembic/versions/0016_evaluation_engine_schema.py`
  * `tests/unit/backend/modules/evaluation/test_calibration_engine.py`
  * `tests/unit/backend/modules/evaluation/test_eval_runner.py`
  * `tests/unit/backend/modules/evaluation/test_golden_manager.py`
  * `tests/integration/test_evaluation_api.py`

---

## 48. Cross-Phase Consistency Review

Phase 15 consumes identical `correlation_id`, `tenant_id`, and `ReliabilityScoreDTO` formats from Phase 13 (`scoring`) and publishes standardized `EvaluationSummaryDTO` payloads consumed directly by Phase 16 (`dashboard`) without structural impedance.

---

## 49. Enterprise Design Review Summary

* **SOLID**: Single responsibility enforced by separating dataset management (`GoldenDatasetManager`), evaluation orchestration (`ContinuousEvalRunner`), and statistical analysis (`ScoreCalibrationEngine`).
* **Clean Architecture**: Providers (`RagasProvider`) are completely hidden behind `EvaluationMetricProvider` interfaces.
* **Async-First**: Batch evaluation jobs execute inside Celery worker processes protecting real-time API performance.

---

## 50. Final Deliverables Summary

* **Folder Structure**: Build out `api/`, `models/`, `providers/`, `repositories/`, `schemas/`, `services/` inside `backend/modules/evaluation/`.
* **Database**: Migration `0016_evaluation_engine_schema.py` creating `golden_datasets`, `golden_items`, and `evaluation_jobs`.
* **API Inventory**: `POST /api/v1/evaluation/datasets`, `POST /api/v1/evaluation/jobs/run`, `GET /api/v1/evaluation/jobs/{job_id}`.
* **Milestone Scripts**: `impl_m15_part1.py`, `impl_m15_part2.py`, `impl_m15_part3.py`, `impl_m15_tests.py`.
