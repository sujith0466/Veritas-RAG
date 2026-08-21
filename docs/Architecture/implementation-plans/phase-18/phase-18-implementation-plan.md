# Phase 18 Implementation Plan — Autonomous Self-Healing & Fallback Governor (Production Grade)

**Phase Name:** Phase 18 — Autonomous Self-Healing & Fallback Governor
**Target Module:** `backend/modules/reliability/`
**Status:** Planning & Architecture Baseline (Approved for Future Script-Based Implementation)
**Author:** Veritas RAG Principal Architecture & Enterprise QA Team

---

## 1. Executive Summary

Phase 18 delivers the enterprise **Autonomous Self-Healing & Fallback Governor** (`backend/modules/reliability/`), elevating the Phase 4 circuit breaker (`CircuitBreakerEngine`) and fallback router (`FallbackRouter`) into an intelligent, closed-loop self-healing controller. Phase 18 introduces `SelfHealingGovernor`, which monitors real-time Phase 13 scoring trends, circuit breaker state changes, and Phase 17 alerts. When systemic degradation is detected, the Governor executes autonomous remediations: dynamically tuning retrieval hyperparameters (`AdaptiveParameterTuner`), rotating degraded AI model providers seamlessly (`ModelRotationOrchestrator`), and launching background recovery sweeps to re-process quarantined vector chunks (`QuarantineRecoveryWorker`). All remediation decisions and policy rules persist cleanly via `alembic` migration `0018`.

---

## 2. Phase Objectives

1. **Closed-Loop Self-Healing Governor**: Monitor system events to trigger autonomous remediation policies (`SelfHealingPolicyORM`) when reliability metrics degrade across a rolling window.
2. **Adaptive Parameter Tuning**: Automatically adjust runtime hyperparameters (`retrieval_top_k`, `similarity_threshold`, `max_retry_budget`, `reflection_strictness`) to counteract transient noise or low recall.
3. **Provider Model Rotation**: Orchestrate seamless fallback rotations (`ModelRotationOrchestrator`) from primary providers (e.g., OpenAI) to secondary models (Anthropic/Azure/Local VLLM) when rate limits or circuit breakers trip.
4. **Quarantine Recovery Sweeps**: Schedule background self-healing workers (`QuarantineRecoveryWorker`) that automatically re-index and restore items from Phase 14 `quarantine_chunks` after model upgrades.
5. **Observability & API Controls**: Expose governance endpoints (`/api/v1/reliability/governor/*`) and maintain an immutable audit trail of every automated intervention (`HealingActionLogORM`).

---

## 3. Business Goals

* **Autonomous 99.99% Uptime**: Eliminate late-night engineering pages by allowing the AI infrastructure to self-diagnose and heal around transient vendor outages or embedding drifts.
* **Cost vs. Quality Optimization**: Automatically downgrade to lower-cost/faster secondary models during extreme traffic spikes while ensuring strict SLA compliance.
* **Zero-Intervention Recovery**: Automatically clear quarantined data backlogs without requiring manual database intervention or manual script execution.

---

## 4. Technical Goals

* **Extend Existing Reliability Module**: Build directly inside `backend/modules/reliability/` extending `services/reliability_gateway.py`, `circuit_breaker/engine.py`, and `fallbacks/router.py`.
* **Stateful Distributed Governor**: Coordinate self-healing policies using Redis distributed state (`raguard:healing:state:{tenant_id}`) to prevent multiple backend instances from triggering conflicting rotations simultaneously.
* **Idempotent Recovery Actions**: Guarantee that every automated tuning or rotation execution is idempotent and fully reversible (`rollback_action()`).

---

## 5. Scope

* Extension of schemas (`backend/modules/reliability/schemas/reliability_dto.py` and `errors.py`).
* Implementation of `SelfHealingGovernor` (`services/governor.py`).
* Implementation of `AdaptiveParameterTuner` (`services/tuner.py`).
* Implementation of `ModelRotationOrchestrator` (`fallbacks/model_rotation.py`).
* Implementation of `QuarantineRecoveryWorker` (`workers/recovery_worker.py`).
* ORM entities (`models/self_healing_policy.py`, `models/healing_action_log.py`) and migration `alembic/versions/0018_self_healing_governor.py`.
* REST API endpoints (`api/governor_routes.py`).

---

## 6. Out of Scope

* Raw vector generation or initial document ingestion (governed by Phase 1).
* Human-in-the-loop manual ticket workflows in Jira (governed by Phase 17 webhook dispatching).
* Frontend dashboard rendering (governed by Phase 16).

---

## 7. PRD Alignment

Aligns directly with PRD Section 8.1 (*Autonomous Closed-Loop Self-Healing and Dynamic Fallbacks*), establishing the automated governor responsible for real-time infrastructure resilience.

---

## 8. Architecture Alignment

Strictly adheres to `AI_ARCHITECTURE_AFTER_IMPROVEMENTS.md` and `ARCHITECTURE_AFTER_IMPROVEMENTS.md`. It acts as the self-adjusting control loop supervising the Phase 4 `ReliabilityGateway`.

---

## 9. Dependency Analysis

* **Upstream Dependencies**:
  * Phase 4 (`circuit_breaker`, `fallbacks`): Baseline state engines.
  * Phase 13 (`scoring`): Real-time composite `final_score` and `trust_classification`.
  * Phase 14 (`knowledge_health`): `quarantine_chunks` table anomalies.
  * Phase 17 (`alerts`): Emits `CircuitBreakerTrippedEvent` and `HallucinationSpikeEvent`.
* **Downstream Dependencies**:
  * Phase 16 (`dashboard`): Displays active healing actions and hyperparameter adaptations.

---

## 10. Existing Codebase Review

* `backend/modules/reliability/services/reliability_gateway.py`: Orchestrates Phase 4 fallback logic and calls `CircuitBreakerEngine`.
* `backend/modules/reliability/circuit_breaker/engine.py`: Manages state machine (`CLOSED`, `OPEN`, `HALF_OPEN`).
* `backend/modules/reliability/fallbacks/router.py`: Handles zero-result fallback strategies.
* **Justification for New Components**: Existing code only reacts to hard errors by returning static fallbacks or opening circuits. Phase 18 adds closed-loop proactive tuning, automated model provider switching, and quarantine background restoration.

---

## 11. High-Level Architecture

```
Events (Circuit Breakers / Score Drops / Quarantine Alerts)
            │
            ▼
┌──────────────────────────────────────────────────────────────┐
│ SelfHealingGovernor (Phase 18 Closed-Loop Controller)        │
│  ├─► AdaptiveParameterTuner (Adjust top-k, retry, strictness)│
│  ├─► ModelRotationOrchestrator (Rotate LLM/Embedding models) │
│  └─► QuarantineRecoveryWorker (Re-process quarantined chunks)│
└──────────────────────────────────────────────────────────────┘
            │
            ▼
    HealingActionLogORM (`healing_actions_log`) + Config Overrides
```

---

## 12. Low-Level Design

### Adaptive Parameter Tuning Matrix
When consecutive Phase 13 evaluation scores drop below `70.0` over $N=5$ requests:
1. **Low Recall Diagnosis** (`coverage_score < 0.5`): `AdaptiveParameterTuner` increments `retrieval_top_k` from $5 \to 10$ and decreases `similarity_threshold` from $0.75 \to 0.68$.
2. **High Conflict Diagnosis** (`conflict_score > 0.4`): `AdaptiveParameterTuner` increments `reflection_strictness` and boosts `max_retry_budget` from $2 \to 3$.
3. All adjustments persist to Redis key `raguard:tuning:overrides:{tenant_id}` with a `2-hour` decay TTL before reverting to baseline defaults.

### Model Rotation Protocol
When `CircuitBreakerEngine` transitions provider $P_1$ (`openai`) to `OPEN`:
1. `ModelRotationOrchestrator` queries healthy secondary providers $P_2 \in \{\text{azure}, \text{anthropic}, \text{vllm}\}$.
2. Updates tenant route configuration dynamically in Redis.
3. Records intervention in `healing_actions_log` with `action_type = "MODEL_ROTATION"`.

---

## 13. Component Design

1. **`SelfHealingGovernor`**: Master domain service coordinating trigger analysis and remediation dispatch.
2. **`AdaptiveParameterTuner`**: Calculates and applies hyperparameter modifications.
3. **`ModelRotationOrchestrator`**: Manages multi-provider fallback switching.
4. **`QuarantineRecoveryWorker`**: Background Celery task sweeping `quarantine_chunks` and testing re-ingestion.

---

## 14. Module Responsibilities

| Module / Class | Responsibility |
| :--- | :--- |
| `schemas/reliability_dto.py` | Add `HealingActionDTO`, `SelfHealingPolicyDTO`, `ParameterTuningCommandDTO`. |
| `services/governor.py` | Evaluates system degradation and triggers remediation handlers. |
| `services/tuner.py` | Modifies runtime retrieval and reflection parameters dynamically. |
| `fallbacks/model_rotation.py` | Switches active LLM/embedding endpoints upon circuit breaker open events. |
| `workers/recovery_worker.py` | Batch background job restoring quarantined vector chunks. |
| `models/self_healing_policy.py`| ORM entities `SelfHealingPolicyORM` & `HealingActionLogORM`. |

---

## 15. Data Flow

1. `CircuitBreakerTrippedEvent(provider="openai")` arrives at `SelfHealingGovernor`.
2. Governor loads `SelfHealingPolicyORM` for tenant.
3. Policy mandates `auto_rotate_provider = True`.
4. `ModelRotationOrchestrator.rotate_provider("openai")` selects `"azure-openai"` and updates routing cache.
5. `HealingActionLogORM` persists the switch; `SelfHealingInterventionEvent` is emitted.
6. When `"openai"` recovers (`CircuitBreaker` returns to `CLOSED`), `rollback_action()` restores primary routing.

---

## 16. Sequence Diagrams

```
EventBus -> SelfHealingGovernor: on_event(CircuitBreakerTrippedEvent)
activate SelfHealingGovernor
SelfHealingGovernor -> PolicyRepo: fetch_policy(tenant_id)
PolicyRepo --> SelfHealingGovernor: policy_orm
SelfHealingGovernor -> ModelRotationOrch: rotate_provider(failed_provider)
ModelRotationOrch -> Redis: get_healthy_backup_provider()
Redis --> ModelRotationOrch: "anthropic"
ModelRotationOrch -> Redis: set("route_override:" + tenant_id, "anthropic", ttl=3600)
ModelRotationOrch --> SelfHealingGovernor: rotation_result=SUCCESS
SelfHealingGovernor -> HealingRepo: log_action("MODEL_ROTATION", details)
SelfHealingGovernor -> EventBus: publish(SelfHealingInterventionEvent)
deactivate SelfHealingGovernor
```

---

## 17. Folder Structure Changes

```
backend/modules/reliability/
├── __init__.py
├── api/
│   ├── __init__.py
│   ├── governor_routes.py        # [NEW] Governor management routes
│   └── routes.py                 # [PRESERVED] Phase 4 baseline routes
├── circuit_breaker/              # [PRESERVED] Phase 4 baseline
├── events/                       # [PRESERVED] Phase 4 baseline
├── fallbacks/
│   ├── __init__.py
│   ├── model_rotation.py         # [NEW] Multi-model rotation engine
│   ├── router.py                 # [PRESERVED]
│   └── zero_result.py            # [PRESERVED]
├── models/
│   ├── __init__.py
│   ├── healing_action_log.py     # [NEW] ORM for intervention records
│   └── self_healing_policy.py    # [NEW] ORM for governor rules
├── repositories/
│   ├── __init__.py
│   └── governor_repository.py    # [NEW] Repository layer
├── schemas/
│   ├── __init__.py
│   ├── errors.py                 # [MODIFY] Add Governor exceptions
│   └── reliability_dto.py        # [MODIFY] Add Governor DTOs
├── services/
│   ├── __init__.py
│   ├── governor.py               # [NEW] Closed-loop controller
│   ├── reliability_gateway.py    # [MODIFY] Hook governor overrides
│   └── tuner.py                  # [NEW] Adaptive parameter tuner
└── workers/
    ├── __init__.py
    └── recovery_worker.py        # [NEW] Quarantine recovery worker
```

---

## 18. File Creation Plan

| File Path | Type | Justification / Purpose |
| :--- | :--- | :--- |
| `backend/modules/reliability/schemas/errors.py` | Modify | Add `SelfHealingPolicyError`, `RotationFailedError`. |
| `backend/modules/reliability/schemas/reliability_dto.py` | Modify | Add `HealingActionDTO`, `SelfHealingPolicyDTO`, `ParameterOverrideDTO`. |
| `backend/modules/reliability/services/tuner.py` | New | Implements `AdaptiveParameterTuner`. |
| `backend/modules/reliability/fallbacks/model_rotation.py` | New | Implements `ModelRotationOrchestrator`. |
| `backend/modules/reliability/services/governor.py` | New | Implements `SelfHealingGovernor`. |
| `backend/modules/reliability/workers/recovery_worker.py` | New | Async Celery worker `QuarantineRecoveryWorker`. |
| `backend/modules/reliability/models/self_healing_policy.py` | New | ORM entity `SelfHealingPolicyORM`. |
| `backend/modules/reliability/models/healing_action_log.py` | New | ORM entity `HealingActionLogORM`. |
| `backend/modules/reliability/repositories/governor_repository.py` | New | Repository for policies and action logs. |
| `backend/modules/reliability/api/governor_routes.py` | New | FastAPI endpoints (`/api/v1/reliability/governor/*`). |
| `backend/modules/reliability/services/reliability_gateway.py` | Modify | Hook parameter tuning overrides from Redis. |
| `alembic/versions/0018_self_healing_governor.py` | New | Migration creating `self_healing_policies` & `healing_actions_log`. |

---

## 19. Database Changes

### Table: `self_healing_policies`
| Column Name | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | UUID | PRIMARY KEY | Policy ID |
| `tenant_id` | VARCHAR(64) | NOT NULL, INDEX | Tenant namespace |
| `auto_parameter_tuning`| BOOLEAN | NOT NULL | Enable `AdaptiveParameterTuner` |
| `auto_model_rotation` | BOOLEAN | NOT NULL | Enable `ModelRotationOrchestrator` |
| `auto_quarantine_sweep`| BOOLEAN| NOT NULL | Enable `QuarantineRecoveryWorker` |
| `max_interventions_per_hour`| INTEGER| NOT NULL | Throttling limit (default `10`) |

### Table: `healing_actions_log`
| Column Name | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | UUID | PRIMARY KEY | Intervention ID |
| `tenant_id` | VARCHAR(64) | NOT NULL, INDEX | Tenant namespace |
| `action_type` | VARCHAR(64) | NOT NULL | `PARAMETER_TUNE`, `MODEL_ROTATION`, `QUARANTINE_RECOVERY` |
| `trigger_reason` | TEXT | NOT NULL | Why intervention fired |
| `changes_applied` | JSONB | NOT NULL | Exact overrides (`top_k=10`, `provider=azure`) |
| `is_rolled_back` | BOOLEAN | NOT NULL | Rollback status |
| `executed_at` | TIMESTAMP | NOT NULL | Execution timestamp |

---

## 20. API Design

| Method | Endpoint | Request Body | Response DTO | Summary |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/reliability/governor/policies` | N/A (`?tenant_id=...`) | `SelfHealingPolicyDTO` | Fetch active self-healing configuration |
| `PUT` | `/api/v1/reliability/governor/policies` | `SelfHealingPolicyUpdateDTO`| `SelfHealingPolicyDTO` | Update self-healing automation toggles |
| `GET` | `/api/v1/reliability/governor/actions` | N/A (`?page=1&size=20`) | `list[HealingActionDTO]` | Retrieve historical intervention audit logs |
| `POST` | `/api/v1/reliability/governor/actions/{id}/rollback` | N/A | `HealingActionDTO` | Manually roll back an active self-healing intervention |

---

## 21. Configuration Changes

Add to `configs/app_config.py`:
* `GOVERNOR_TUNING_DECAY_TTL_SEC`: Default `7200` (2 hours).
* `GOVERNOR_MAX_INTERVENTIONS_HOUR`: Default `10`.
* `GOVERNOR_RECOVERY_BATCH_SIZE`: Default `100`.

---

## 22. Environment Variables

| Variable Name | Default | Description |
| :--- | :--- | :--- |
| `RAGUARD_GOVERNOR_TUNING_TTL` | `7200` | Expiration time for adaptive parameter overrides |
| `RAGUARD_GOVERNOR_ENABLED` | `true` | Feature flag enabling self-healing interventions |
| `RAGUARD_GOVERNOR_MAX_HOUR` | `10` | Maximum autonomous interventions allowed per hour |

---

## 23. Security Considerations

* **Tenant Isolation**: Policy overrides and intervention logs MUST strictly filter queries and Redis cache keys (`raguard:tuning:overrides:{tenant_id}`) by `tenant_id`.
* **Throttling Guard**: `SelfHealingGovernor` MUST check count of `healing_actions_log` over the last 60 minutes and block new interventions if `count >= max_interventions_per_hour` to prevent oscillation loops.

---

## 24. Performance Considerations

* **Sub-Millisecond Override Fetch**: `ReliabilityGateway` MUST read active hyperparameter overrides (`AdaptiveParameterTuner`) from Redis (`MGET`) during query pipeline initialization in $< 1\text{ms}$.
* **Background Recovery Sweeps**: `QuarantineRecoveryWorker` executes exclusively inside Celery worker queues, processing items in chunks of `100` to avoid slamming Qdrant vectors.

---

## 25. Monitoring Strategy

* **OpenTelemetry Tracing**: Record span `raguard.governor.intervene` recording `action_type`, `changes_applied`, and `tenant_id`.
* **Prometheus Metrics**:
  * `raguard_healing_interventions_total{tenant_id, action_type}`
  * `raguard_active_model_rotations_gauge{tenant_id, target_provider}`
  * `raguard_quarantine_items_recovered_total{tenant_id}`

---

## 26. Error Handling Strategy

* Raise `RotationFailedError` if `ModelRotationOrchestrator` finds all backup AI providers un-pingable or also in `OPEN` circuit state.
* If `QuarantineRecoveryWorker` encounters persistent errors re-indexing a quarantined chunk, increment `retry_count` column on `quarantine_chunks` and skip item cleanly without crashing worker.

---

## 27. Testing Strategy

* **Unit Tests**: Verify `AdaptiveParameterTuner` math and boundary clamping (`top_k` clamped between `3` and `25`); verify `SelfHealingGovernor` throttling counter check.
* **Integration Tests**: Verify model rotation routing overrides inside `ReliabilityGateway` using mocked Redis instances and verify REST endpoints `/api/v1/reliability/governor/*`.
* **Regression Tests**: Verify that Phase 4 baseline fallback execution remains identical when `RAGUARD_GOVERNOR_ENABLED=false`.

---

## 28. Unit Testing Plan

* `tests/unit/backend/modules/reliability/test_governor.py`: Test trigger threshold evaluation and rate-limit throttling checks.
* `tests/unit/backend/modules/reliability/test_tuner.py`: Test dynamic `top_k` and `similarity_threshold` scaling and rollback.
* `tests/unit/backend/modules/reliability/test_model_rotation.py`: Verify primary-to-backup model switching and routing key persistence.

---

## 29. Integration Testing Plan

* `tests/integration/test_governor_api.py`: Verify `SelfHealingPolicyORM` CRUD operations and manual rollback execution.
* `tests/integration/test_quarantine_recovery_worker.py`: Verify Celery task sweeping `quarantine_chunks` and testing vector restoration.

---

## 30. Risk Assessment

| Risk | Likelihood | Impact | Mitigation Strategy |
| :--- | :--- | :--- | :--- |
| Parameter oscillation (`top_k` bouncing between 5 and 15) | Medium | Medium | Enforce mandatory `2-hour` cooldown/decay window (`raguard:tuning:overrides`) before allowing another parameter change. |
| Rotated backup provider also experiencing outage | Low | High | Maintain priority fallback list (`azure` $\to$ `anthropic` $\to$ `local-vllm`) inside `ModelRotationOrchestrator`. |

---

## 31. Acceptance Criteria

1. `SelfHealingGovernor` catches `CircuitBreakerTrippedEvent` and automatically rotates active provider via `ModelRotationOrchestrator` within `< 10ms`.
2. `AdaptiveParameterTuner` writes exact hyperparameter overrides to Redis when consecutive low-score alerts arrive, successfully modifying `ReliabilityGateway` behavior.
3. Every intervention is logged to `healing_actions_log` and can be manually rolled back via `POST /api/v1/reliability/governor/actions/{id}/rollback`.

---

## 32. Completion Criteria

* All code committed inside `backend/modules/reliability/`.
* Alembic migration `0018_self_healing_governor.py` applied.
* 100% of Phase 18 unit and integration tests passing alongside all Phase 0–17 tests.

---

## 33. Milestone Breakdown

* **Milestone 1 (`impl_m18_part1.py`)**: DTO extensions (`reliability_dto.py`, `errors.py`), ORM models, and migration `0018_self_healing_governor.py`.
* **Milestone 2 (`impl_m18_part2.py`)**: Implement `AdaptiveParameterTuner` and `ModelRotationOrchestrator`.
* **Milestone 3 (`impl_m18_part3.py`)**: Implement `SelfHealingGovernor`, `QuarantineRecoveryWorker`, and REST API (`api/governor_routes.py`).
* **Milestone 4 (`impl_m18_tests.py`)**: Execute unit (`test_governor.py`, `test_tuner.py`) and integration tests.

---

## 34. Provider Abstraction

Model provider switching is completely decoupled through `ModelRotationOrchestrator`, which dynamically updates target provider identifiers consumed by Phase 5 (`retrieval`) and Phase 10 (`generation`).

---

## 35. Architecture Decision Records (ADR)

* **ADR-018-1**: Store runtime hyperparameter overrides (`retrieval_top_k`, `similarity_threshold`) in Redis (`raguard:tuning:overrides:{tenant_id}`) with a 2-hour TTL rather than modifying persistent database configurations, ensuring clean automatic decay if the system stabilizes.
* **ADR-018-2**: Enforce a hard hourly intervention quota (`max_interventions_per_hour = 10`) inside `SelfHealingGovernor` to guarantee protection against automated runaway oscillation loops.

---

## 36. Versioning Strategy

All governor REST endpoints and DTO schemas use API `v1` (`SelfHealingPolicyDTO`, `HealingActionDTO`), preserving exact compatibility with baseline Phase 4 `reliability` endpoints.

---

## 37. Feature Flags

`RAGUARD_GOVERNOR_ENABLED`: If set to `false`, `SelfHealingGovernor.on_event()` ignores all incoming anomaly events and `AdaptiveParameterTuner` overrides are ignored.

---

## 38. Performance Budgets

* Redis override parameter lookup (`MGET`): `< 1ms`.
* Model rotation routing update: `< 5ms`.
* Governor event evaluation & logging: `< 15ms`.

---

## 39. Deployment Architecture

`SelfHealingGovernor` runs within backend API containers. `QuarantineRecoveryWorker` runs inside Celery worker pools (`celery worker -Q maintenance`).

---

## 40. Failure Recovery Matrix

| Failure Scenario | Detection Mechanism | Recovery Behavior |
| :--- | :--- | :--- |
| Redis Unreachable During Override Read | `RedisError` | Log warning, catch inside `ReliabilityGateway`, and use static baseline app_config defaults (`fail-safe`). |
| Backup Provider Rotation Fails | `RotationFailedError` | Log critical error, emit alert via Phase 17 (`SlackChannel`), and fall back to Phase 4 `ZeroResultFallback`. |

---

## 41. Dependency Graph

```
Phases 4, 13, 14, 17 ──► SelfHealingGovernor ──► ReliabilityGateway Overrides & Model Rotation
                               │
                               ▼
            PostgreSQL (`healing_actions_log`, `self_healing_policies`)
```

---

## 42. Rollback Strategy

Set `RAGUARD_GOVERNOR_ENABLED=false` to stop autonomous interventions. Run `alembic downgrade 0017` to drop governor tables cleanly.

---

## 43. Success Metrics

* **Self-Healing Success Rate**: $> 90\%$ of transient circuit breaker openings resolved automatically via model rotation without user disruption.
* **Oscillation Prevention**: $100\%$ adherence to `max_interventions_per_hour` limits.
* **Override Lookup Speed**: $99\text{th}$ percentile Redis tuning check latency $< 1\text{ms}$.

---

## 44. Traceability Matrix

| Requirement | PRD Reference | Architecture Document | Implementing Class |
| :--- | :--- | :--- | :--- |
| Closed-Loop Governor | Section 8.1 | `AI_ARCHITECTURE_AFTER_IMPROVEMENTS.md` | `SelfHealingGovernor` |
| Adaptive Hyperparameter Tuning | Section 8.1 | `ARCHITECTURE_AFTER_IMPROVEMENTS.md` | `AdaptiveParameterTuner` |
| Multi-Provider Model Rotation | Section 8.1 | `API_DESIGN_AFTER_IMPROVEMENTS.md` | `ModelRotationOrchestrator` |

---

## 45. Implementation Checklist

- [ ] Modify `schemas/errors.py` and `schemas/reliability_dto.py`.
- [ ] Create `services/tuner.py`, `fallbacks/model_rotation.py`, and `services/governor.py`.
- [ ] Create `workers/recovery_worker.py` and update `services/reliability_gateway.py`.
- [ ] Create `models/self_healing_policy.py`, `models/healing_action_log.py`, `repositories/governor_repository.py`, and `api/governor_routes.py`.
- [ ] Create migration `0018_self_healing_governor.py`.

---

## 46. Phase Completion Checklist

- [ ] All 4 implementation milestones (`impl_m18_*.py`) executed cleanly.
- [ ] 100% of Phase 18 unit and integration tests passing (`test_governor*.py`).
- [ ] Zero static analysis errors (`mypy`, `ruff`).
- [ ] Complete preservation of Phase 4 baseline circuit breaker behavior.

---

## 47. File Inventory

* **Modified Files**:
  * `backend/modules/reliability/schemas/reliability_dto.py`
  * `backend/modules/reliability/schemas/errors.py`
  * `backend/modules/reliability/services/reliability_gateway.py`
* **New Files**:
  * `backend/modules/reliability/services/governor.py`
  * `backend/modules/reliability/services/tuner.py`
  * `backend/modules/reliability/fallbacks/model_rotation.py`
  * `backend/modules/reliability/workers/recovery_worker.py`
  * `backend/modules/reliability/models/self_healing_policy.py`
  * `backend/modules/reliability/models/healing_action_log.py`
  * `backend/modules/reliability/repositories/governor_repository.py`
  * `backend/modules/reliability/api/governor_routes.py`
  * `alembic/versions/0018_self_healing_governor.py`
  * `tests/unit/backend/modules/reliability/test_governor.py`
  * `tests/unit/backend/modules/reliability/test_tuner.py`
  * `tests/unit/backend/modules/reliability/test_model_rotation.py`
  * `tests/integration/test_governor_api.py`
  * `tests/integration/test_quarantine_recovery_worker.py`

---

## 48. Cross-Phase Consistency Review

Phase 18 seamlessly supervises Phase 4 (`ReliabilityGateway`), consumes Phase 13/14 metrics, and publishes remediations visible inside Phase 16 (`dashboard`), closing the active governance loop across the Veritas RAG ecosystem.

---

## 49. Enterprise Design Review Summary

* **SOLID**: Clear separation between decisioning (`SelfHealingGovernor`), parameter tuning (`AdaptiveParameterTuner`), model routing (`ModelRotationOrchestrator`), and background recovery (`QuarantineRecoveryWorker`).
* **Clean Architecture**: Domain governor logic remains completely decoupled from specific AI provider SDK implementations.
* **Resilience**: Rate limits, decay windows, and fail-safe defaults guarantee stability under extreme anomaly conditions.

---

## 50. Final Deliverables Summary

* **Folder Structure**: Add `fallbacks/model_rotation.py`, `api/governor_routes.py`, `services/governor.py`, `services/tuner.py`, and `workers/recovery_worker.py` inside `backend/modules/reliability/`.
* **Database**: Migration `0018_self_healing_governor.py` creating `self_healing_policies` and `healing_actions_log`.
* **API Inventory**: `GET /api/v1/reliability/governor/policies`, `PUT /api/v1/reliability/governor/policies`, `GET /api/v1/reliability/governor/actions`, `POST /api/v1/reliability/governor/actions/{id}/rollback`.
* **Milestone Scripts**: `impl_m18_part1.py`, `impl_m18_part2.py`, `impl_m18_part3.py`, `impl_m18_tests.py`.
