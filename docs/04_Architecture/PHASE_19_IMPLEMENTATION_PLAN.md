# Phase 19 Implementation Plan — Enterprise Multi-Tenant Analytics & ROI Engine (Production Grade)

**Phase Name:** Phase 19 — Enterprise Multi-Tenant Analytics & ROI Engine  
**Target Module:** `backend/modules/analytics/`  
**Status:** Planning & Architecture Baseline (Approved for Future Script-Based Implementation)  
**Author:** RAGuard Principal Architecture & Enterprise QA Team  

---

## 1. Executive Summary

Phase 19 delivers the **Enterprise Multi-Tenant Analytics & ROI Engine** (`backend/modules/analytics/`), extending the Phase 4 baseline (`QueryAnalyticsService`, `ReportingService`) into a comprehensive financial attribution, token metering, and predictive forecasting authority. Phase 19 introduces exact token tracking (`TokenUsageORM`) across embedding (`Phase 1`), retrieval (`Phase 5`), and generation (`Phase 10`) pipelines, calculating financial costs via a configurable pricing engine (`PricingEngine`). Equipped with `ROIAttributionEngine` and `TrendForecaster`, Phase 19 quantifies organizational cost avoidance (support hours saved vs. blocked hallucinations) and forecasts 90-day multi-tenant storage and token budgets (`alembic` migration `0019`).

---

## 2. Phase Objectives

1. **Granular Token & Cost Metering**: Track exact prompt, completion, and embedding token counts per tenant, provider, and model (`TokenUsageORM`) with micro-dollar cost calculation (`PricingEngine`).
2. **Financial ROI & Value Attribution**: Quantify tangible enterprise value (`ROIAttributionDTO`) across automated query resolutions, engineering hours saved, and hallucination risk mitigation savings.
3. **Multi-Tenant Quota Governance**: Enforce monthly token and cost budgets (`QuotaGovernor`), emitting warning events at 80% thresholds and throttling requests upon budget exhaustion.
4. **Predictive Trend Forecasting**: Project 90-day usage growth, cost trajectories, and vector storage requirements using statistical regression (`TrendForecaster`).
5. **Observability & REST APIs**: Expose financial and metering endpoints (`/api/v1/analytics/roi/*`, `/api/v1/analytics/quotas/*`) for tenant billing and executive reporting.

---

## 3. Business Goals

* **Prove Generative AI ROI**: Provide CFOs and business leaders with defensible, dollar-quantified metrics proving that RAGuard deployment reduces overall enterprise support costs.
* **Prevent Bill Shock**: Enforce hard and soft multi-tenant budget boundaries so high-volume API spikes never result in unexpected cloud/LLM provider charges.
* **Transparent Chargeback**: Enable IT departments to accurately allocate AI infrastructure costs across internal business units (`tenant_id` billing namespaces).

---

## 4. Technical Goals

* **Extend Existing Analytics Package**: Build cleanly inside `backend/modules/analytics/` adding `services/pricing.py`, `services/roi.py`, `services/quota.py`, and `services/forecaster.py` while preserving Phase 4 contracts.
* **High-Throughput Asynchronous Metering**: Record token consumption records asynchronously in background tasks (`record_token_usage_task`) so billing checks never slow down the critical query serving path.
* **Redis Quota Tracking**: Enforce atomic quota incrementation (`INCRBYFLOAT`) inside Redis to guarantee real-time budget tracking across horizontal backend replicas.

---

## 5. Scope

* Extension of schemas (`backend/modules/analytics/schemas/analytics_dto.py` and `errors.py`).
* Implementation of `PricingEngine` (`services/pricing.py`).
* Implementation of `ROIAttributionEngine` (`services/roi.py`).
* Implementation of `QuotaGovernor` (`services/quota.py`).
* Implementation of `TrendForecaster` (`services/forecaster.py`).
* ORM entities (`models/token_usage.py`, `models/tenant_quota.py`) and migration `alembic/versions/0019_enterprise_roi_analytics.py`.
* REST API endpoints (`api/roi_routes.py`, `api/quota_routes.py`).

---

## 6. Out of Scope

* Direct credit card billing or Stripe/Adyen merchant payment integration (governed by external ERP systems).
* Raw generation inference execution (governed by Phase 10).
* Dashboard UI visual chart components (governed by Phase 16).

---

## 7. PRD Alignment

Aligns directly with PRD Section 9.1 (*Enterprise Multi-Tenant Analytics, ROI Attribution, and Predictive Metering*), establishing the financial metering and forecasting foundation of RAGuard AI.

---

## 8. Architecture Alignment

Strictly adheres to `ARCHITECTURE_AFTER_IMPROVEMENTS.md` and `API_DESIGN_AFTER_IMPROVEMENTS.md`. It acts as the financial metrics layer sitting alongside the Phase 4 query analytics engine.

---

## 9. Dependency Analysis

* **Upstream Dependencies**:
  * Phase 1 (`ingestion`/`embedding`): Emits embedding token consumption events.
  * Phase 10 (`generation`): Emits LLM prompt and completion token counts.
  * Phase 13 (`scoring`): Provides confidence and hallucination interception counts.
* **Downstream Dependencies**:
  * Phase 16 (`dashboard`): Visualizes ROI charts and quota utilization gauges.

---

## 10. Existing Codebase Review

* `backend/modules/analytics/services/analytics_service.py`: Tracks query execution outcomes, duration, confidence, and reliability scores.
* `backend/modules/analytics/services/reporting_service.py`: Generates executive aggregation reports over query analytics tables.
* **Justification for New Components**: Existing services measure technical quality and latency. Phase 19 adds the financial metering layer required for enterprise billing chargeback, dollar-denominated ROI attribution, and quota gating.

---

## 11. High-Level Architecture

```
LLM & Embedding Invocations (Phases 1, 5, 10)
               │
               ▼
┌──────────────────────────────────────────────────────────────┐
│ QuotaGovernor (Checks Redis budgets before execution)        │
│  ├─► PricingEngine (Calculates micro-dollar costs)           │
│  ├─► ROIAttributionEngine (Computes support hours & savings) │
│  └─► TrendForecaster (Projects 90-day financial growth)      │
└──────────────────────────────────────────────────────────────┘
               │
               ▼
 TokenUsageORM (`token_usages`) + TenantQuotaORM (`tenant_quotas`)
```

---

## 12. Low-Level Design

### Cost Calculation Matrix
For tokens consumed $N_p$ (prompt) and $N_c$ (completion) on provider/model $M$:
$$\text{Cost}(M) = \left( N_p \times C_{\text{prompt}}(M) \right) + \left( N_c \times C_{\text{completion}}(M) \right)$$
Where $C_{\text{prompt}}$ and $C_{\text{completion}}$ are stored per 1,000 tokens inside `PricingEngine` (e.g., GPT-4o: \$0.005 / \$0.015).

### ROI Dollar Attribution ($V_{\text{ROI}}$)
Let $Q_{\text{trusted}}$ be queries answered with `is_safe_to_serve == True`, $H_{\text{blocked}}$ be intercepted hallucinations (`ABORTED_HALLUCINATION`), $C_{\text{ticket}}$ be baseline human support ticket cost (default \$18.50), and $C_{\text{incident}}$ be average compliance investigation cost (default \$250.00):
$$V_{\text{ROI}} = (Q_{\text{trusted}} \times C_{\text{ticket}}) + (H_{\text{blocked}} \times C_{\text{incident}}) - \text{Total\_LLM\_Cost}$$

---

## 13. Component Design

1. **`PricingEngine`**: Manages model cost tables and computes exact transaction values.
2. **`QuotaGovernor`**: Validates remaining monthly token and cost allocations.
3. **`ROIAttributionEngine`**: Synthesizes dollar-savings summaries and engineering hour efficiencies.
4. **`TrendForecaster`**: Performs linear and exponential least-squares regressions over historical billing data.

---

## 14. Module Responsibilities

| Module / Class | Responsibility |
| :--- | :--- |
| `schemas/analytics_dto.py` | Add `ROIAttributionDTO`, `TokenUsageDTO`, `TenantQuotaDTO`, `TrendForecastDTO`. |
| `services/pricing.py` | Calculates micro-dollar costs across embedding and LLM calls. |
| `services/quota.py` | Enforces budget limits using Redis atomic increments. |
| `services/roi.py` | Computes enterprise value attribution formulas. |
| `services/forecaster.py` | Projects 90-day cost and usage trajectories. |
| `models/token_usage.py` | ORM entities `TokenUsageORM` & `TenantQuotaORM`. |

---

## 15. Data Flow

1. Incoming query arrives; `ExecutionGateway` calls `QuotaGovernor.check_quota(tenant_id, estimated_tokens=1500)`.
2. `QuotaGovernor` reads remaining budget from Redis (`raguard:quota:monthly:{tenant_id}`); returns `allowed=True`.
3. Query executes; `ExecutionGateway` emits `TokenConsumedEvent(prompt=500, completion=200, model="gpt-4o")`.
4. `PricingEngine` calculates `total_cost = $0.0055`.
5. Background worker saves record to `TokenUsageORM` and atomically decrements Redis quota.
6. Client queries `GET /api/v1/analytics/roi/{tenant_id}`; `ROIAttributionEngine` aggregates savings.

---

## 16. Sequence Diagrams

```
Gateway -> QuotaGovernor: check_and_reserve(tenant_id, est_tokens)
activate QuotaGovernor
QuotaGovernor -> Redis: DECRBY("quota:tokens:" + tenant_id, est_tokens)
Redis --> QuotaGovernor: remaining_tokens
alt remaining_tokens >= 0
  QuotaGovernor --> Gateway: QuotaCheckResult(allowed=True)
else quota exhausted
  QuotaGovernor -> Redis: INCRBY("quota:tokens:" + tenant_id, est_tokens)
  QuotaGovernor --> Gateway: QuotaCheckResult(allowed=False, reason="QUOTA_EXHAUSTED")
end
deactivate QuotaGovernor

Gateway -> ExecutionPipeline: run()
ExecutionPipeline --> Gateway: result (actual_prompt, actual_completion)
Gateway -> PricingEngine: record_usage_async(tenant_id, actual_tokens, model)
PricingEngine -> PricingEngine: compute_cost(actual_tokens, model)
PricingEngine -> AnalyticsRepo: save_token_usage(usage_orm)
PricingEngine -> Redis: adjust_reservation_diff(tenant_id, est_tokens - actual_tokens)
```

---

## 17. Folder Structure Changes

```
backend/modules/analytics/
├── __init__.py
├── api/
│   ├── __init__.py
│   ├── quota_routes.py           # [NEW] Quota management endpoints
│   ├── roi_routes.py             # [NEW] ROI attribution endpoints
│   └── routes.py                 # [PRESERVED] Phase 4 baseline routes
├── models/
│   ├── __init__.py
│   ├── query_analytics.py        # [PRESERVED] Phase 4 baseline
│   ├── tenant_quota.py           # [NEW] ORM for monthly tenant budgets
│   └── token_usage.py            # [NEW] ORM for granular token logs
├── repositories/
│   ├── __init__.py
│   └── analytics_repository.py   # [MODIFY] Add quota and token CRUD
├── schemas/
│   ├── __init__.py
│   ├── analytics_dto.py          # [MODIFY] Add ROI and Quota DTOs
│   └── errors.py                 # [MODIFY] Add QuotaExceededError
└── services/
    ├── __init__.py
    ├── analytics_service.py      # [PRESERVED] Phase 4 baseline
    ├── forecaster.py             # [NEW] 90-day predictive trend engine
    ├── pricing.py                # [NEW] Model pricing calculator
    ├── quota.py                  # [NEW] Budget enforcement governor
    ├── reporting_service.py      # [PRESERVED] Phase 4 baseline
    └── roi.py                    # [NEW] Financial attribution engine
```

---

## 18. File Creation Plan

| File Path | Type | Justification / Purpose |
| :--- | :--- | :--- |
| `backend/modules/analytics/schemas/errors.py` | Modify | Add `QuotaExceededError`, `InvalidPricingModelError`. |
| `backend/modules/analytics/schemas/analytics_dto.py` | Modify | Add `ROIAttributionDTO`, `TokenUsageDTO`, `TenantQuotaDTO`, `TrendForecastDTO`. |
| `backend/modules/analytics/services/pricing.py` | New | Implements `PricingEngine`. |
| `backend/modules/analytics/services/quota.py` | New | Implements `QuotaGovernor`. |
| `backend/modules/analytics/services/roi.py` | New | Implements `ROIAttributionEngine`. |
| `backend/modules/analytics/services/forecaster.py` | New | Implements `TrendForecaster`. |
| `backend/modules/analytics/models/token_usage.py` | New | ORM entity `TokenUsageORM`. |
| `backend/modules/analytics/models/tenant_quota.py` | New | ORM entity `TenantQuotaORM`. |
| `backend/modules/analytics/repositories/analytics_repository.py` | Modify | Add CRUD methods for `token_usages` and `tenant_quotas`. |
| `backend/modules/analytics/api/roi_routes.py` | New | FastAPI endpoints (`/api/v1/analytics/roi/*`). |
| `backend/modules/analytics/api/quota_routes.py` | New | FastAPI endpoints (`/api/v1/analytics/quotas/*`). |
| `alembic/versions/0019_enterprise_roi_analytics.py` | New | Migration creating `token_usages` & `tenant_quotas`. |

---

## 19. Database Changes

### Table: `token_usages`
| Column Name | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | UUID | PRIMARY KEY | Usage log ID |
| `tenant_id` | VARCHAR(64) | NOT NULL, INDEX | Tenant namespace |
| `correlation_id` | VARCHAR(128) | NOT NULL, INDEX | Associated query trace |
| `provider` | VARCHAR(64) | NOT NULL | `openai`, `anthropic`, `azure` |
| `model_name` | VARCHAR(128) | NOT NULL | `gpt-4o`, `text-embedding-3-large` |
| `prompt_tokens` | INTEGER | NOT NULL | Input token count |
| `completion_tokens`| INTEGER| NOT NULL | Output token count |
| `total_cost_usd` | FLOAT | NOT NULL | Micro-dollar cost (`0.005210`) |
| `created_at` | TIMESTAMP | NOT NULL | Execution timestamp |

### Table: `tenant_quotas`
| Column Name | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `tenant_id` | VARCHAR(64) | PRIMARY KEY | Tenant namespace |
| `monthly_token_limit`| BIGINT | NOT NULL | Maximum monthly token allowance |
| `monthly_budget_usd` | FLOAT | NOT NULL | Dollar spending ceiling |
| `warning_threshold_pct`| FLOAT| NOT NULL | Alert trigger level (default `0.80`) |
| `is_hard_enforced` | BOOLEAN | NOT NULL | If `true`, block queries at 100% |

---

## 20. API Design

| Method | Endpoint | Request Body | Response DTO | Summary |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/analytics/roi/{tenant_id}` | N/A (`?window=30d`) | `ROIAttributionDTO` | Fetch comprehensive dollar-savings and hours efficiency report |
| `GET` | `/api/v1/analytics/quotas/{tenant_id}` | N/A | `TenantQuotaDTO` | Fetch remaining token and dollar budget allocations |
| `PUT` | `/api/v1/analytics/quotas/{tenant_id}` | `TenantQuotaUpdateDTO`| `TenantQuotaDTO` | Update monthly spending limits and enforcement flags |
| `GET` | `/api/v1/analytics/roi/{tenant_id}/forecast` | N/A (`?days=90`) | `TrendForecastDTO` | Retrieve 90-day cost and storage trajectory projections |

---

## 21. Configuration Changes

Add to `configs/app_config.py`:
* `ROI_TICKET_SAVINGS_USD`: Default `18.50`.
* `ROI_HALLUCINATION_INCIDENT_USD`: Default `250.00`.
* `QUOTA_DEFAULT_MONTHLY_TOKENS`: Default `10000000` (10M tokens).

---

## 22. Environment Variables

| Variable Name | Default | Description |
| :--- | :--- | :--- |
| `RAGUARD_ROI_TICKET_COST` | `18.50` | Baseline dollar cost of human support ticket handling |
| `RAGUARD_ROI_INCIDENT_COST` | `250.00` | Estimated risk cost per blocked hallucination incident |
| `RAGUARD_QUOTA_ENFORCEMENT_ENABLED` | `true` | Feature flag enabling budget reservation gating |

---

## 23. Security Considerations

* **Tenant Namespace Security**: Quota checks and ROI aggregations MUST enforce strict tenant authorization checks; one tenant must never view or exhaust another tenant's token pool.
* **Pricing Manipulation Protection**: Pricing model tables inside `PricingEngine` MUST be loaded from read-only application configs or restricted admin-only database tables.

---

## 24. Performance Considerations

* **Sub-Millisecond Quota Reservation**: `QuotaGovernor.check_quota()` MUST execute via atomic Redis Lua scripts (`evalsha`) reading and decrementing `quota:tokens:{tenant_id}` in $< 1\text{ms}$.
* **Async Usage Logging**: Token usage persistence to PostgreSQL (`TokenUsageORM`) runs in background asyncio worker tasks without adding latency to the user response payload.

---

## 25. Monitoring Strategy

* **OpenTelemetry Tracing**: Record span `raguard.analytics.quota_check` recording `allowed`, `remaining_tokens`, and `tenant_id`.
* **Prometheus Metrics**:
  * `raguard_tokens_consumed_total{tenant_id, provider, model}`
  * `raguard_cost_incurred_usd_total{tenant_id, model}`
  * `raguard_quota_rejections_total{tenant_id, reason}`

---

## 26. Error Handling Strategy

* Raise `QuotaExceededError` with HTTP `429 Too Many Requests` when a tenant exceeds a hard-enforced monthly token budget.
* If Redis quota cache becomes unavailable (`RedisConnectionError`), log structural warning and fall back to `allow-by-default` (`fail-open`) to prevent blocking production queries during Redis restarts.

---

## 27. Testing Strategy

* **Unit Tests**: Verify `PricingEngine` micro-dollar precision floating-point math across different token splits; test `QuotaGovernor` boundary condition when quota exactly reaches `0`.
* **Integration Tests**: Verify end-to-end quota reservation and usage recording across API calls; verify `ROIAttributionEngine` formula calculations.
* **Regression Tests**: Ensure Phase 4 baseline `QueryAnalyticsService` query history and latency trend queries continue operating without schema conflicts.

---

## 28. Unit Testing Plan

* `tests/unit/backend/modules/analytics/test_pricing.py`: Test pricing table lookup and cost math across embedding and chat models.
* `tests/unit/backend/modules/analytics/test_quota.py`: Test reservation, refunding unused token difference, and hard limit enforcement.
* `tests/unit/backend/modules/analytics/test_roi.py`: Verify dollar-savings formula calculation against simulated query and hallucination counts.

---

## 29. Integration Testing Plan

* `tests/integration/test_roi_api.py`: Verify `/api/v1/analytics/roi/*` endpoint response structures and forecasting accuracy.
* `tests/integration/test_quota_api.py`: Verify quota updates and subsequent HTTP `429` rejection when budget is exhausted.

---

## 30. Risk Assessment

| Risk | Likelihood | Impact | Mitigation Strategy |
| :--- | :--- | :--- | :--- |
| LLM provider changing per-token pricing suddenly | Medium | Medium | Decouple pricing tables into external JSON/database structures (`PricingEngine`) supporting timestamped versioned rates. |
| Redis quota drift from PostgreSQL actual logs | Low | Medium | Schedule a nightly reconciliation cron job syncing Redis quota counters with `SUM(total_tokens)` from `token_usages`. |

---

## 31. Acceptance Criteria

1. `QuotaGovernor` rejects queries with `QuotaExceededError` (`HTTP 429`) the exact moment a tenant's cumulative usage exceeds `monthly_token_limit` when `is_hard_enforced == True`.
2. `ROIAttributionEngine` outputs mathematically verifiable `ROIAttributionDTO` summaries reflecting exact dollar savings based on `ticket_cost` and `incident_cost` parameters.
3. Every LLM and embedding invocation records exact token counts and micro-dollar costs inside `token_usages`.

---

## 32. Completion Criteria

* All code committed inside `backend/modules/analytics/`.
* Alembic migration `0019_enterprise_roi_analytics.py` applied.
* 100% of Phase 19 unit and integration tests passing alongside all Phase 0–18 tests.

---

## 33. Milestone Breakdown

* **Milestone 1 (`impl_m19_part1.py`)**: DTO extensions (`analytics_dto.py`, `errors.py`), `PricingEngine`, ORM models, and migration `0019_enterprise_roi_analytics.py`.
* **Milestone 2 (`impl_m19_part2.py`)**: Implement `QuotaGovernor` and `ROIAttributionEngine`.
* **Milestone 3 (`impl_m19_part3.py`)**: Implement `TrendForecaster` and REST API endpoints (`api/roi_routes.py`, `api/quota_routes.py`).
* **Milestone 4 (`impl_m19_tests.py`)**: Execute unit (`test_pricing.py`, `test_quota.py`, `test_roi.py`) and integration tests.

---

## 34. Provider Abstraction

Metering operates cleanly across all provider types (`openai`, `anthropic`, `azure`, `local`) by extracting universal `usage.prompt_tokens` and `usage.completion_tokens` fields normalized via Phase 10 provider wrappers.

---

## 35. Architecture Decision Records (ADR)

* **ADR-019-1**: Execute quota checks via atomic Redis Lua scripts (`check_and_reserve`) prior to query processing to prevent concurrent request bursts from exceeding hard budget ceilings.
* **ADR-019-2**: Standardize financial ROI calculations around explicit, tenant-configurable unit economics (`ticket_cost_usd`, `incident_cost_usd`) to ensure executive credibility across varying industry sectors.

---

## 36. Versioning Strategy

All financial and metering contracts are exposed under API `v1` (`ROIAttributionDTO`, `TenantQuotaDTO`), preserving full backward compatibility with Phase 4 reporting endpoints.

---

## 37. Feature Flags

`RAGUARD_QUOTA_ENFORCEMENT_ENABLED`: If set to `false`, `QuotaGovernor.check_quota()` immediately returns `allowed = True` for all tenants regardless of consumption.

---

## 38. Performance Budgets

* Quota reservation check: `< 1ms`.
* Token usage async persistence: `< 5ms`.
* ROI 30-day aggregation report fetch: `< 20ms`.

---

## 39. Deployment Architecture

`PricingEngine`, `QuotaGovernor`, and `ROIAttributionEngine` run statelessly within backend containers. Redis clusters host both quota tracking keys and distributed locks cleanly.

---

## 40. Failure Recovery Matrix

| Failure Scenario | Detection Mechanism | Recovery Behavior |
| :--- | :--- | :--- |
| Redis Down During Quota Check | `RedisConnectionError` | Catch exception, log structural warning, return `allowed = True` (`fail-open`) to preserve uptime. |
| Async Usage Save Timeout | `OperationalError` | Enqueue failed token usage payload into local fallback SQLite buffer for subsequent Celery retry ingestion. |

---

## 41. Dependency Graph

```
Phases 1, 5, 10 ──► QuotaGovernor & PricingEngine ──► Phase 19 (ROI & Analytics Store)
                                                               │
                                                               ▼
                            PostgreSQL (`token_usages`, `tenant_quotas`)
```

---

## 42. Rollback Strategy

Set `RAGUARD_QUOTA_ENFORCEMENT_ENABLED=false` to stop budget gating instantly. Run `alembic downgrade 0018` to drop token and quota tables cleanly.

---

## 43. Success Metrics

* **Billing Accuracy**: $100\%$ reconciliation match between `TokenUsageORM` cost summaries and official monthly cloud/LLM vendor invoices.
* **Quota Enforcement Precision**: Zero budget overruns beyond `monthly_token_limit` when hard gating is enabled.
* **API Overhead**: Mean latency overhead added by quota verification $< 1\text{ms}$.

---

## 44. Traceability Matrix

| Requirement | PRD Reference | Architecture Document | Implementing Class |
| :--- | :--- | :--- | :--- |
| Granular Token & Cost Metering | Section 9.1 | `DATABASE_DESIGN_AFTER_IMPROVEMENTS.md` | `PricingEngine` |
| Financial ROI Attribution | Section 9.1 | `AI_ARCHITECTURE_AFTER_IMPROVEMENTS.md` | `ROIAttributionEngine` |
| Multi-Tenant Quota Governance | Section 9.1 | `ARCHITECTURE_AFTER_IMPROVEMENTS.md` | `QuotaGovernor` |

---

## 45. Implementation Checklist

- [ ] Modify `schemas/errors.py` and `schemas/analytics_dto.py`.
- [ ] Create `services/pricing.py`, `services/quota.py`, `services/roi.py`, and `services/forecaster.py`.
- [ ] Create `models/token_usage.py`, `models/tenant_quota.py`, and update `repositories/analytics_repository.py`.
- [ ] Create `api/roi_routes.py` and `api/quota_routes.py`.
- [ ] Create migration `0019_enterprise_roi_analytics.py`.

---

## 46. Phase Completion Checklist

- [ ] All 4 implementation milestones (`impl_m19_*.py`) executed cleanly.
- [ ] 100% of Phase 19 unit and integration tests passing (`test_pricing*.py`, `test_quota*.py`, `test_roi*.py`).
- [ ] Zero static analysis errors (`mypy`, `ruff`).
- [ ] Complete preservation of Phase 4 baseline query analytics behavior.

---

## 47. File Inventory

* **Modified Files**:
  * `backend/modules/analytics/schemas/analytics_dto.py`
  * `backend/modules/analytics/schemas/errors.py`
  * `backend/modules/analytics/repositories/analytics_repository.py`
* **New Files**:
  * `backend/modules/analytics/services/pricing.py`
  * `backend/modules/analytics/services/quota.py`
  * `backend/modules/analytics/services/roi.py`
  * `backend/modules/analytics/services/forecaster.py`
  * `backend/modules/analytics/models/token_usage.py`
  * `backend/modules/analytics/models/tenant_quota.py`
  * `backend/modules/analytics/api/roi_routes.py`
  * `backend/modules/analytics/api/quota_routes.py`
  * `alembic/versions/0019_enterprise_roi_analytics.py`
  * `tests/unit/backend/modules/analytics/test_pricing.py`
  * `tests/unit/backend/modules/analytics/test_quota.py`
  * `tests/unit/backend/modules/analytics/test_roi.py`
  * `tests/integration/test_roi_api.py`
  * `tests/integration/test_quota_api.py`

---

## 48. Cross-Phase Consistency Review

Phase 19 integrates seamlessly across Phase 1 (`embedding`), Phase 5 (`retrieval`), and Phase 10 (`generation`) by capturing uniform token payloads, while delivering financial DTOs directly consumed by Phase 16 (`dashboard`) without schema transforms.

---

## 49. Enterprise Design Review Summary

* **SOLID**: Metering (`PricingEngine`), gating (`QuotaGovernor`), financial modeling (`ROIAttributionEngine`), and forecasting (`TrendForecaster`) operate as isolated, single-purpose classes.
* **Clean Architecture**: Domain financial calculation is strictly decoupled from database persistence and HTTP controller layers.
* **Performance**: Sub-millisecond Redis reservation scripts ensure billing enforcement never compromises query SLA targets.

---

## 50. Final Deliverables Summary

* **Folder Structure**: Add `api/roi_routes.py`, `api/quota_routes.py`, `services/pricing.py`, `services/quota.py`, `services/roi.py`, and `services/forecaster.py` inside `backend/modules/analytics/`.
* **Database**: Migration `0019_enterprise_roi_analytics.py` creating `token_usages` and `tenant_quotas`.
* **API Inventory**: `GET /api/v1/analytics/roi/{tenant_id}`, `GET /api/v1/analytics/quotas/{tenant_id}`, `PUT /api/v1/analytics/quotas/{tenant_id}`, `GET /api/v1/analytics/roi/{tenant_id}/forecast`.
* **Milestone Scripts**: `impl_m19_part1.py`, `impl_m19_part2.py`, `impl_m19_part3.py`, `impl_m19_tests.py`.
