# Phase 16 Implementation Plan — AI Reliability & Governance Dashboard (Production Grade)

**Phase Name:** Phase 16 — AI Reliability & Governance Dashboard
**Target Module:** `backend/modules/dashboard/`
**Status:** Planning & Architecture Baseline (Approved for Future Script-Based Implementation)
**Author:** RAGuard Principal Architecture & Enterprise QA Team

---

## 1. Executive Summary

Phase 16 delivers the enterprise **AI Reliability & Governance Dashboard** (`backend/modules/dashboard/`), extending the Phase 3 baseline (`DashboardService`) into a unified real-time telemetry, trust classification visualization, and compliance export portal. Phase 16 ingests live scoring events (`Phase 13`), knowledge health indices (`Phase 14`), evaluation benchmark trends (`Phase 15`), and hallucination interception logs (`Phase 11/12`) to provide low-latency websocket live feeds (`/api/v1/dashboard/live/{tenant_id}`), SLA compliance metrics (`SLAComplianceReportDTO`), trust distribution histograms (`TrustDistributionDTO`), and auditable regulatory export bundles (CSV/JSON). All queries are backed by high-performance Redis caching (`RedisDashboardCache`) ensuring sub-20ms dashboard render speeds under high tenant concurrency.

---

## 2. Phase Objectives

1. **Real-Time Live Feed & Websockets**: Provide low-latency websocket connections (`/api/v1/dashboard/ws/{tenant_id}`) and polling endpoints (`LiveFeedService`) streaming live query evaluations, trust classifications, and security interception events.
2. **Trust Tier Distribution Breakdown**: Aggregate real-time distributions across `VERIFIED_TRUSTED`, `DEGRADED_CAUTION`, and `UNRELIABLE_REJECT` classifications across customizable time windows (`1h`, `24h`, `7d`, `30d`).
3. **SLA Compliance & Hallucination Trends**: Compute hourly/daily time-series trends tracking hallucination interception rates and SLA adherence against target safety thresholds.
4. **Compliance Audit Export**: Implement `AuditExportService` to generate cryptographically verified, tamper-evident compliance export packages (`AuditExportBundleDTO`) in CSV and JSON formats for regulators.
5. **High-Concurrency Caching**: Protect relational query analytics (`query_analytics`, `scoring_logs`) via multi-tier Redis caching with short-window invalidation (`15s` TTL).

---

## 3. Business Goals

* **Single-Pane-of-Glass Governance**: Empower Chief Risk Officers (CROs), AI Ethics leads, and compliance officers with instantaneous visibility into generative AI safety across the entire organization.
* **Audit Readiness**: Reduce compliance audit preparation time from weeks to seconds via one-click export of complete claim-by-claim verification trails.
* **Proactive SLA Enforcement**: Instantly visualize trust classification dips and reliability drift before customer-facing incidents occur.

---

## 4. Technical Goals

* **Extend Existing Dashboard Service**: Build directly upon `backend/modules/dashboard/services/dashboard_service.py` by adding governance, live-feed, and export capabilities while preserving baseline summary contracts.
* **Non-Blocking Caching Architecture**: Enforce read-through caching (`RedisDashboardCache`) across heavy aggregate SQL queries so dashboard polling never blocks core API query handling.
* **Async Websocket Streaming**: Implement FastAPI websocket route handlers using `EventDispatcher` hooks (`LiveEventBroadcaster`) with automatic heartbeat ping-ponging (`keepalive=30s`).

---

## 5. Scope

* Extension of schemas in `backend/modules/dashboard/schemas/dashboard_dto.py` (`SLAComplianceReportDTO`, `TrustDistributionDTO`, `HallucinationTrendDTO`, `AuditExportRequestDTO`, `AuditExportBundleDTO`).
* Implementation of `LiveFeedService` & `LiveEventBroadcaster` (`backend/modules/dashboard/services/live_feed.py`).
* Implementation of `AuditExportService` (`backend/modules/dashboard/services/audit_export.py`).
* Implementation of `RedisDashboardCache` (`backend/modules/dashboard/services/cache_service.py`).
* Extension of `DashboardService` (`services/dashboard_service.py`).
* REST API routes (`api/routes.py`) and websocket endpoints.

---

## 6. Out of Scope

* Raw data ingestion and underlying score computation (governed by Phases 13, 14, and 15).
* External PagerDuty or Slack alert dispatching (governed by Phase 18).
* Frontend React/Vue UI component coding (backend API contracts and websocket providers only).

---

## 7. PRD Alignment

Aligns directly with PRD Section 7.1 (*Executive AI Reliability & Governance Dashboard*), establishing the comprehensive backend aggregation, streaming, and export services required for enterprise AI visibility.

---

## 8. Architecture Alignment

Strictly adheres to `ARCHITECTURE_AFTER_IMPROVEMENTS.md` and `API_DESIGN_AFTER_IMPROVEMENTS.md`. It acts as the read-optimized presentation layer sitting atop the analytics, scoring, and evaluation data stores.

---

## 9. Dependency Analysis

* **Upstream Dependencies**:
  * Phase 4 (`analytics`): `QueryAnalyticsRecord` table (`total_duration_ms`, `outcome`, `confidence_score`).
  * Phase 13 (`scoring`): `ScoringLogORM` table (`trust_classification`, `final_score`, `is_safe_to_serve`).
  * Phase 14 (`knowledge_health`): `KnowledgeHealthIndexDTO` and scan summaries.
  * Phase 15 (`evaluation`): `EvaluationJobORM` benchmarks and calibration curves.
* **Downstream Dependencies**:
  * Phase 18 (`alerts`): Triggers operational notifications when dashboard SLA compliance drops below target tiers.

---

## 10. Existing Codebase Review

* `backend/modules/dashboard/services/dashboard_service.py`: Implements `get_knowledge_intelligence_summary()` and `get_executive_dashboard()` over `QueryAnalyticsRecord` and `DocumentChunk`.
* `backend/modules/dashboard/api/routes.py`: Exposes `/api/v1/dashboard/executive` and `/api/v1/dashboard/knowledge`.
* **Justification for New Components**: Existing endpoints provide high-level summaries over 24-hour windows. Phase 16 requires real-time streaming, historical multi-tier trust distributions, trend forecasting, and regulatory compliance export generation.

---

## 11. High-Level Architecture

```
Phases 13, 14, 15 Events ──► LiveEventBroadcaster ──► Websocket (`/ws/{tenant_id}`)
                                      ▲
                                      │ (Read-Through Cache / 15s TTL)
Query / Scoring Logs ──────► DashboardService & Cache ──► REST (`/governance`, `/trends`)
                                      │
                                      ▼
                             AuditExportService ──────► Regulatory Export (CSV/JSON)
```

---

## 12. Low-Level Design

### Trust Distribution & SLA Calculation
For time window $T$, total evaluations $N$:
* **Trust Distribution**:
  $$P(\text{tier}) = \frac{|\{e \in T \mid e.\text{trust\_classification} == \text{tier}\}|}{N} \times 100.0$$
* **SLA Compliance Rate**:
  $$\text{SLA}_{\text{rate}} = \frac{|\{e \in T \mid e.\text{is\_safe\_to\_serve} == \text{True} \land e.\text{total\_duration\_ms} \le \text{SLA\_limit}\}|}{N} \times 100.0$$

### Websocket Event Multiplexer
`LiveEventBroadcaster` listens to `EventDispatcher` for domain events (`ReliabilityScoreComputedEvent`, `ReflectionCompletedEvent`). Upon receipt, it formats the event payload into a `LiveDashboardEventDTO` and broadcasts concurrently to all active websocket connections registered for `event.tenant_id`.

---

## 13. Component Design

1. **`DashboardService`**: Core aggregation engine extended with governance and time-series breakdown queries.
2. **`LiveFeedService` & `LiveEventBroadcaster`**: Manages real-time event subscriptions, polling buffers, and websocket connection pools.
3. **`AuditExportService`**: Compiles multi-table audit histories into zip/tar or JSON packages with SHA-256 checksum headers.
4. **`RedisDashboardCache`**: Wraps SQLAlchemy aggregate queries with key-based Redis expiration policies.

---

## 15. Data Flow

1. Client requests `GET /api/v1/dashboard/governance/{tenant_id}?window=24h`.
2. `DashboardService` checks `RedisDashboardCache.get("governance:{tenant_id}:24h")`.
3. If cache miss, `DashboardService` executes optimized group-by SQL queries over `scoring_logs` and `query_analytics`.
4. Result DTO (`SLAComplianceReportDTO`) is cached for `15 seconds` and returned to client.
5. In parallel, `LiveEventBroadcaster` pushes real-time `ReliabilityScoreComputedEvent` payloads to connected websocket clients.

---

## 16. Sequence Diagrams

```
Client -> RouteHandler: GET /governance/tenant_abc?window=24h
activate RouteHandler
RouteHandler -> DashboardService: get_governance_report(tenant_abc, "24h")
DashboardService -> RedisCache: get("gov:tenant_abc:24h")
RedisCache --> DashboardService: None (cache miss)
DashboardService -> ScoringRepo: aggregate_trust_distribution(tenant_abc, window)
DashboardService -> AnalyticsRepo: aggregate_sla_metrics(tenant_abc, window)
ScoringRepo --> DashboardService: trust_counts
AnalyticsRepo --> DashboardService: sla_stats
DashboardService -> RedisCache: set("gov:tenant_abc:24h", report_dto, ttl=15)
DashboardService --> RouteHandler: SLAComplianceReportDTO
RouteHandler --> Client: 200 OK + JSON
deactivate RouteHandler
```

---

## 17. Folder Structure Changes

```
backend/modules/dashboard/
├── __init__.py
├── api/
│   ├── __init__.py
│   ├── routes.py                 # [MODIFY] Add governance, trends, export routes
│   └── websocket.py              # [NEW] Websocket streaming controller
├── schemas/
│   ├── __init__.py
│   ├── errors.py                 # [NEW] Dashboard exceptions
│   └── dashboard_dto.py          # [MODIFY] Add governance/export schemas
└── services/
    ├── __init__.py
    ├── audit_export.py           # [NEW] Compliance export engine
    ├── cache_service.py          # [NEW] Redis caching wrapper
    ├── dashboard_service.py      # [MODIFY] Extend with governance aggregations
    └── live_feed.py              # [NEW] Websocket & polling broadcaster
```

---

## 18. File Creation Plan

| File Path | Type | Justification / Purpose |
| :--- | :--- | :--- |
| `backend/modules/dashboard/schemas/errors.py` | New | Defines `ExportGenerationError`, `InvalidWindowError`. |
| `backend/modules/dashboard/schemas/dashboard_dto.py` | Modify | Add `SLAComplianceReportDTO`, `TrustDistributionDTO`, `AuditExportBundleDTO`. |
| `backend/modules/dashboard/services/cache_service.py` | New | Implements `RedisDashboardCache`. |
| `backend/modules/dashboard/services/live_feed.py` | New | Implements `LiveFeedService` & `LiveEventBroadcaster`. |
| `backend/modules/dashboard/services/audit_export.py` | New | Implements `AuditExportService`. |
| `backend/modules/dashboard/services/dashboard_service.py` | Modify | Extend with `get_governance_summary()` and `get_trust_trends()`. |
| `backend/modules/dashboard/api/routes.py` | Modify | Add REST endpoints for governance, trust trends, and exports. |
| `backend/modules/dashboard/api/websocket.py` | New | FastAPI websocket handler `/api/v1/dashboard/ws/{tenant_id}`. |

---

## 19. Database Changes

No new database tables are required for Phase 16. The dashboard operates exclusively as a read-optimized query and caching layer over existing tables (`scoring_logs`, `query_analytics`, `evaluation_jobs`, `reflection_logs`).

---

## 20. API Design

| Method | Endpoint | Request Body | Response DTO | Summary |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/dashboard/governance/{tenant_id}` | N/A (`?window=24h`) | `SLAComplianceReportDTO` | Fetch SLA compliance and trust distribution summary |
| `GET` | `/api/v1/dashboard/trends/{tenant_id}` | N/A (`?window=7d`) | `list[HallucinationTrendDTO]` | Fetch time-series hallucination interception trends |
| `POST` | `/api/v1/dashboard/export` | `AuditExportRequestDTO` | `AuditExportBundleDTO` | Generate tamper-evident compliance export bundle |
| `WS` | `/api/v1/dashboard/ws/{tenant_id}` | Websocket Handshake | `LiveDashboardEventDTO` stream | Real-time websocket stream of live pipeline evaluations |

---

## 21. Configuration Changes

Add to `configs/app_config.py`:
* `DASHBOARD_CACHE_TTL_SEC`: Default `15`.
* `DASHBOARD_WS_HEARTBEAT_SEC`: Default `30`.
* `DASHBOARD_EXPORT_MAX_RECORDS`: Default `10000`.

---

## 22. Environment Variables

| Variable Name | Default | Description |
| :--- | :--- | :--- |
| `RAGUARD_DASHBOARD_CACHE_TTL_SEC` | `15` | Redis cache expiration for aggregate queries |
| `RAGUARD_DASHBOARD_WS_ENABLED` | `true` | Feature flag enabling real-time websocket broadcasting |
| `RAGUARD_DASHBOARD_EXPORT_LIMIT` | `10000` | Maximum rows permitted per audit export bundle |

---

## 23. Security Considerations

* **Tenant Isolation**: Every REST query and websocket subscription MUST verify JWT tenant claims against requested `tenant_id` namespace.
* **Sensitive Export Guard**: `AuditExportService` MUST strip or mask user-identifiable raw query text if `mask_pii=True` is requested in `AuditExportRequestDTO`.

---

## 24. Performance Considerations

* **Indexed Time-Series Queries**: All aggregate SQL queries over `scoring_logs` and `query_analytics` MUST utilize composite indices `(tenant_id, created_at)` to guarantee sub-20ms database scan times.
* **Non-Blocking Exports**: If `AuditExportRequestDTO.date_range` spans $> 1,000$ records, `AuditExportService` offloads zip file generation to a background Celery worker and returns `202 Accepted` with a download URL.

---

## 25. Monitoring Strategy

* **OpenTelemetry Tracing**: Record span `raguard.dashboard.governance` recording `cache_hit` and `query_duration_ms`.
* **Prometheus Metrics**:
  * `raguard_dashboard_cache_hits_total{tenant_id}`
  * `raguard_dashboard_active_websockets_gauge{tenant_id}`
  * `raguard_dashboard_export_jobs_total{status}`

---

## 26. Error Handling Strategy

* Raise `InvalidWindowError` if client requests unsupported time parameters (`window="999y"`).
* If Redis cache is unreachable (`RedisConnectionError`), log structural warning, bypass cache cleanly, and serve directly from PostgreSQL without returning `500 Internal Server Error`.

---

## 27. Testing Strategy

* **Unit Tests**: Verify `AuditExportService` CSV formatting and SHA-256 checksum calculations; verify `LiveEventBroadcaster` filters events accurately by `tenant_id`.
* **Integration Tests**: Verify end-to-end REST routes (`/api/v1/dashboard/governance/*`) and websocket connection handshakes (`testclient.websocket_connect()`).
* **Regression Tests**: Ensure Phase 3 baseline `/api/v1/dashboard/executive` continues to return exact expected fields.

---

## 28. Unit Testing Plan

* `tests/unit/backend/modules/dashboard/test_cache_service.py`: Verify cache get/set/eviction and fallback when Redis is down.
* `tests/unit/backend/modules/dashboard/test_audit_export.py`: Test CSV/JSON bundling and SHA-256 header validation.
* `tests/unit/backend/modules/dashboard/test_live_feed.py`: Verify websocket multiplexing across multiple concurrent tenant connections.

---

## 29. Integration Testing Plan

* `tests/integration/test_dashboard_governance_api.py`: Verify `SLAComplianceReportDTO` numbers reflect exact populated database state.
* `tests/integration/test_dashboard_websocket.py`: Test real-time message delivery over FastAPI `TestClient` websockets upon event bus publishing.

---

## 30. Risk Assessment

| Risk | Likelihood | Impact | Mitigation Strategy |
| :--- | :--- | :--- | :--- |
| Websocket connection leak under high client traffic | Medium | High | Enforce strict `keepalive=30s` heartbeat checks and automatic socket disconnects upon ping failure. |
| Export queries locking database tables | Low | Medium | Execute audit export queries using read-only database replicas or uncommitted snapshot isolation (`FOR SHARE`). |

---

## 31. Acceptance Criteria

1. `DashboardService.get_governance_report()` returns valid `SLAComplianceReportDTO` with exact percentages matching underlying `scoring_logs`.
2. Websocket endpoints (`/api/v1/dashboard/ws/{tenant_id}`) receive live `ReliabilityScoreComputedEvent` notifications within `< 50ms` of publication.
3. Audit export bundles generate verified CSV files containing exact claim and reflection history.

---

## 32. Completion Criteria

* All code committed inside `backend/modules/dashboard/`.
* 100% of Phase 16 unit and integration tests passing alongside all Phase 0–15 tests.
* Zero static analysis errors (`mypy`, `ruff`).

---

## 33. Milestone Breakdown

* **Milestone 1 (`impl_m16_part1.py`)**: DTO extensions (`dashboard_dto.py`, `errors.py`) and `RedisDashboardCache`.
* **Milestone 2 (`impl_m16_part2.py`)**: Implement `AuditExportService` and extend `DashboardService` with governance & trend queries.
* **Milestone 3 (`impl_m16_part3.py`)**: Implement `LiveFeedService`, `LiveEventBroadcaster`, REST routes (`api/routes.py`), and websocket handler (`api/websocket.py`).
* **Milestone 4 (`impl_m16_tests.py`)**: Execute unit (`test_audit_export.py`, `test_live_feed.py`) and integration tests.

---

## 34. Provider Abstraction

Dashboard services strictly query domain repositories and cache layers without direct external AI provider invocations.

---

## 35. Architecture Decision Records (ADR)

* **ADR-016-1**: Use read-through Redis caching with `15-second` TTL for all aggregate governance queries to prevent dashboard polling from degrading live query throughput.
* **ADR-016-2**: Support both websocket streaming (`/ws`) and HTTP polling (`/live`) to ensure compatibility with restricted corporate firewall environments where websockets are blocked.

---

## 36. Versioning Strategy

All new DTOs are exposed under API `v1` (`SLAComplianceReportDTO`), maintaining strict backward compatibility with existing executive and knowledge summary schemas.

---

## 37. Feature Flags

`RAGUARD_DASHBOARD_WS_ENABLED`: If set to `false`, websocket endpoint `/api/v1/dashboard/ws/{tenant_id}` returns `403 Forbidden (Websockets Disabled)`, directing clients to use HTTP polling.

---

## 38. Performance Budgets

* Cached governance report fetch: `< 5ms`.
* Uncached database aggregation over 24h: `< 25ms`.
* Websocket event broadcast latency: `< 10ms`.

---

## 39. Deployment Architecture

`LiveEventBroadcaster` and websocket handlers run inside the stateless backend API containers. Redis instances serve both distributed locking and dashboard caching namespaces cleanly.

---

## 40. Failure Recovery Matrix

| Failure Scenario | Detection Mechanism | Recovery Behavior |
| :--- | :--- | :--- |
| Redis Cache Unreachable | `RedisError` | Log structural warning, bypass cache entirely, serve directly from PostgreSQL query indices. |
| Client Websocket Disconnect | `WebSocketDisconnect` | Cleanly unregister connection from `LiveEventBroadcaster` pool without throwing server errors. |

---

## 41. Dependency Graph

```
Phases 4, 13, 14, 15 ──► Phase 16 (Dashboard Service & Websockets) ──► Frontend Portal
                                       │
                                       ▼
                       Redis Cache (`gov:{tenant_id}:{window}`)
```

---

## 42. Rollback Strategy

Disable websocket broadcasting via `RAGUARD_DASHBOARD_WS_ENABLED=false`. Code changes to `routes.py` and `dashboard_service.py` can be reverted cleanly without database migration rollbacks.

---

## 43. Success Metrics

* **Dashboard Render Speed**: $99\text{th}$ percentile API latency $< 20\text{ms}$ across all governance routes.
* **Websocket Reliability**: $> 99.9\%$ uptime on live real-time event streaming.
* **Audit Export Integrity**: $100\%$ SHA-256 verification accuracy on generated compliance bundles.

---

## 44. Traceability Matrix

| Requirement | PRD Reference | Architecture Document | Implementing Class |
| :--- | :--- | :--- | :--- |
| Real-Time Websocket Feed | Section 7.1 | `API_DESIGN_AFTER_IMPROVEMENTS.md` | `LiveEventBroadcaster` |
| Trust Distribution Charts | Section 7.1 | `ARCHITECTURE_AFTER_IMPROVEMENTS.md` | `DashboardService` |
| Compliance Audit Exports | Section 7.1 | `AI_ARCHITECTURE_AFTER_IMPROVEMENTS.md` | `AuditExportService` |

---

## 45. Implementation Checklist

- [ ] Create `schemas/errors.py` and update `schemas/dashboard_dto.py`.
- [ ] Create `services/cache_service.py`, `services/live_feed.py`, and `services/audit_export.py`.
- [ ] Update `services/dashboard_service.py` and `api/routes.py`.
- [ ] Create `api/websocket.py`.

---

## 46. Phase Completion Checklist

- [ ] All 4 implementation milestones (`impl_m16_*.py`) executed cleanly.
- [ ] 100% of Phase 16 unit and integration tests passing (`test_dashboard_*.py`).
- [ ] Zero static analysis errors (`mypy`, `ruff`).
- [ ] Complete preservation of Phase 3 baseline dashboard endpoints.

---

## 47. File Inventory

* **Modified Files**:
  * `backend/modules/dashboard/schemas/dashboard_dto.py`
  * `backend/modules/dashboard/services/dashboard_service.py`
  * `backend/modules/dashboard/api/routes.py`
* **New Files**:
  * `backend/modules/dashboard/schemas/errors.py`
  * `backend/modules/dashboard/services/cache_service.py`
  * `backend/modules/dashboard/services/live_feed.py`
  * `backend/modules/dashboard/services/audit_export.py`
  * `backend/modules/dashboard/api/websocket.py`
  * `tests/unit/backend/modules/dashboard/test_cache_service.py`
  * `tests/unit/backend/modules/dashboard/test_audit_export.py`
  * `tests/unit/backend/modules/dashboard/test_live_feed.py`
  * `tests/integration/test_dashboard_governance_api.py`
  * `tests/integration/test_dashboard_websocket.py`

---

## 48. Cross-Phase Consistency Review

Phase 16 aggregates terminology across all preceding phases (`VERIFIED_TRUSTED`, `DEGRADED_CAUTION`, `UNRELIABLE_REJECT` from Phase 13; `KnowledgeHealthIndexDTO` from Phase 14; `EvaluationSummaryDTO` from Phase 15), providing a unified executive presentation layer.

---

## 49. Enterprise Design Review Summary

* **SOLID**: Caching (`RedisDashboardCache`), streaming (`LiveFeedService`), and export compilation (`AuditExportService`) are cleanly separated.
* **Clean Architecture**: API transport layers (Websocket/HTTP) remain fully detached from database aggregation queries.
* **Performance**: Read-through Redis caching with 15s TTL insulates relational tables from concurrent executive reporting loads.

---

## 50. Final Deliverables Summary

* **Folder Structure**: Add `api/websocket.py` and populate `services/cache_service.py`, `services/live_feed.py`, `services/audit_export.py`.
* **API Inventory**: `GET /api/v1/dashboard/governance/{tenant_id}`, `GET /api/v1/dashboard/trends/{tenant_id}`, `POST /api/v1/dashboard/export`, `WS /api/v1/dashboard/ws/{tenant_id}`.
* **Milestone Scripts**: `impl_m16_part1.py`, `impl_m16_part2.py`, `impl_m16_part3.py`, `impl_m16_tests.py`.
