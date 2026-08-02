# Phase 17 Implementation Plan — Real-Time Alerting & Notification Engine (Production Grade)

**Phase Name:** Phase 17 — Real-Time Alerting & Notification Engine
**Target Module:** `backend/modules/alerts/`
**Status:** Planning & Architecture Baseline (Approved for Future Script-Based Implementation)
**Author:** RAGuard Principal Architecture & Enterprise QA Team

---

## 1. Executive Summary

Phase 17 delivers the enterprise **Real-Time Alerting & Notification Engine** (`backend/modules/alerts/`), establishing automated, multi-channel operational alerting triggered by generative AI anomalies across the RAGuard pipeline. Creating the new `backend/modules/alerts/` domain package, Phase 17 implements rule evaluation (`AlertRuleEngine`) and multi-channel dispatch (`SlackChannel`, `PagerDutyChannel`, `EmailChannel`, `WebhookChannel`) behind a unified provider abstraction (`BaseNotificationChannel`). Equipped with Redis-backed alert deduplication (`AlertDeduplicationEngine`) to prevent notification fatigue during high-volume SLA drops, Phase 17 guarantees that SREs and compliance officers are instantly notified when Phase 13 trust scores plummet, Phase 14 quarantine tables overflow, or Phase 11/12 hallucination rates spike (`alembic` migration `0017`).

---

## 2. Phase Objectives

1. **Rule Evaluation Engine**: Evaluate incoming system events (`ReliabilityScoreComputedEvent`, `HallucinationInterceptedEvent`, `CircuitBreakerTrippedEvent`) against customizable tenant alert rules (`AlertRuleORM`).
2. **Multi-Channel Notification Dispatch**: Deliver rich, structured alert notifications across Slack (Block Kit), PagerDuty (Events API v2), SMTP/Email, and custom HMAC-signed HTTPS webhooks.
3. **Alert Deduplication & Cooldowns**: Suppress redundant alert bursts using Redis cooldown keys (`raguard:alert:cooldown:{rule_id}`) and exponential throttling.
4. **Audit History & Lifecycle Tracking**: Persist all triggered alert dispatches, delivery statuses, and acknowledgments to PostgreSQL (`alert_history` table).
5. **REST API Management Portal**: Expose full CRUD management endpoints (`/api/v1/alerts/rules`, `/api/v1/alerts/history`) for tenant rule configuration.

---

## 3. Business Goals

* **Sub-Minute Incident Response**: Ensure engineering and compliance teams receive instant actionable notifications within `< 5 seconds` of a major AI safety violation.
* **Eliminate Alert Fatigue**: Suppress duplicate notification storms during systemic upstream outages via intelligent cooldown suppression.
* **Enterprise Integration**: Seamlessly plug into existing enterprise incident command tools (Slack, PagerDuty, Jira/Webhooks) without custom middleware.

---

## 4. Technical Goals

* **Create Dedicated Alerts Package**: Build `backend/modules/alerts/` adhering strictly to RAGuard modular boundaries (`channels/`, `models/`, `repositories/`, `schemas/`, `services/`).
* **Provider Abstraction**: Enforce `BaseNotificationChannel` (`channels/base.py`) ensuring all delivery transports implement uniform `send_alert(payload: AlertPayloadDTO)` async contracts.
* **Asynchronous Dispatch**: Execute all outbound HTTP webhook and SMTP network calls inside background Celery tasks (`dispatch_alert_task`) to prevent event-bus blocking.

---

## 5. Scope

* Implementation of DTOs in `backend/modules/alerts/schemas/alert_dto.py` and `errors.py`.
* Implementation of `AlertRuleEngine` & `AlertDispatcher` (`services/rule_engine.py`, `services/dispatcher.py`).
* Implementation of `AlertDeduplicationEngine` (`services/deduplication.py`).
* Notification channels (`channels/base.py`, `channels/slack_channel.py`, `channels/pagerduty_channel.py`, `channels/email_channel.py`, `channels/webhook_channel.py`).
* ORM entities (`models/alert_rule.py`, `models/alert_history.py`) and migration `alembic/versions/0017_alerting_engine_schema.py`.
* REST API endpoints (`api/routes.py`).

---

## 6. Out of Scope

* Computing raw underlying scores or health indices (governed by Phases 13, 14, 15).
* Executing automated pipeline rollback actions upon alert trigger (governed by Phase 18).
* Third-party SMS/Twilio cellular dispatching (handled via PagerDuty/webhook routing).

---

## 7. PRD Alignment

Aligns directly with PRD Section 7.2 (*Real-Time Alerting and Multi-Channel Incident Notifications*), mandating automated multi-channel incident dispatching upon SLA and safety breaches.

---

## 8. Architecture Alignment

Strictly adheres to `ARCHITECTURE_AFTER_IMPROVEMENTS.md` and `EVALUATION_FRAMEWORK_AFTER_IMPROVEMENTS.md`. It acts as the event-driven notification authority subscribed to the global RAGuard `EventDispatcher`.

---

## 9. Dependency Analysis

* **Upstream Dependencies**:
  * Phase 11/12 (`reflection`/`validation`): Emits `HallucinationInterceptedEvent`.
  * Phase 13 (`scoring`): Emits `ReliabilityScoreComputedEvent`.
  * Phase 14 (`knowledge_health`): Emits `QuarantineThresholdExceededEvent`.
  * `EventDispatcher` (`backend/core/events/dispatcher.py`): Ingests all system events.
* **Downstream Dependencies**:
  * Phase 16 (`dashboard`): Displays historical triggered alerts in executive activity feeds.

---

## 10. Existing Codebase Review

* `backend/modules/alerts/`: Currently does not exist.
* **Justification for New Components**: Creating this domain package allows clean encapsulation of all alert evaluation rules, deduplication policies, and third-party webhook integrations without polluting core scoring or retrieval modules.

---

## 11. High-Level Architecture

```
EventBus (Score / Hallucination / Quarantine Events)
               │
               ▼
┌──────────────────────────────────────────────────────────────┐
│ AlertRuleEngine (Evaluates conditions against `alert_rules`) │
│  ├─► AlertDeduplicationEngine (Checks Redis cooldown TTLs)   │
│  └─► AlertDispatcher (Routes payload to enabled channels)    │
│       ├─► SlackChannel ───► Slack Webhook (Block Kit)        │
│       ├─► PagerDutyChannel─► PagerDuty Events API v2         │
│       └─► WebhookChannel ──► Signed HMAC Custom Webhook      │
└──────────────────────────────────────────────────────────────┘
               │
               ▼
     AlertHistoryORM (`alert_history` table in PostgreSQL)
```

---

## 12. Low-Level Design

### Alert Rule Evaluation Logic
An `AlertRuleORM` defines a trigger condition:
* `metric_name`: e.g., `"trust_classification"`, `"final_score"`, `"hallucination_outcome"`
* `operator`: e.g., `"EQUALS"`, `"LESS_THAN"`, `"GREATER_THAN"`
* `threshold_value`: e.g., `"UNRELIABLE_REJECT"`, `"65.0"`, `"ABORTED_HALLUCINATION"`
* `cooldown_minutes`: e.g., `15`

When event $E$ arrives:
1. Query active rules for $E.\text{tenant\_id}$ where $E.\text{metric\_name} == \text{rule.metric\_name}$.
2. If `rule.operator(E.value, rule.threshold_value)` evaluates to `True`:
3. Check Redis key $K = \text{"raguard:alert:cooldown:"} + \text{rule.id}$.
4. If $K$ exists, drop event (`DEDUPLICATED`). Else, set $K$ with $\text{TTL} = \text{rule.cooldown\_minutes} \times 60$ and trigger `AlertDispatcher`.

---

## 13. Component Design

1. **`AlertRuleEngine`**: Subscribes to `EventDispatcher` and tests event payloads against database rules.
2. **`AlertDeduplicationEngine`**: Redis-backed cooldown governor suppressing duplicate triggers.
3. **`AlertDispatcher`**: Celery-backed routing engine invoking concrete `BaseNotificationChannel` implementations.
4. **`AlertRepository`**: CRUD operations for rules and historical dispatch records.

---

## 14. Module Responsibilities

| Module / Class | Responsibility |
| :--- | :--- |
| `schemas/alert_dto.py` | Defines `AlertRuleCreateDTO`, `AlertPayloadDTO`, `AlertHistoryDTO`, `ChannelConfigDTO`. |
| `services/rule_engine.py` | Evaluates domain events against tenant alert criteria. |
| `services/deduplication.py` | Manages Redis cooldown keys and throttling counters. |
| `services/dispatcher.py` | Coordinates multi-channel delivery and records `alert_history`. |
| `channels/slack_channel.py` | Formats and transmits Slack Block Kit webhook payloads. |
| `channels/pagerduty_channel.py` | Formats and transmits PagerDuty Events API v2 payloads. |
| `channels/webhook_channel.py` | Formats JSON payload and signs with `HMAC-SHA256` (`X-RAGuard-Signature`). |

---

## 15. Data Flow

1. `ReliabilityScoreComputedEvent(final_score=52.0, trust_classification="UNRELIABLE_REJECT")` is published to event bus.
2. `AlertRuleEngine.on_event()` catches event and loads tenant rules.
3. Rule matching `trust_classification == UNRELIABLE_REJECT` triggers.
4. `AlertDeduplicationEngine.is_in_cooldown(rule.id)` returns `False`.
5. `AlertDispatcher.dispatch(rule, event)` enqueues background task.
6. `SlackChannel.send_alert()` and `PagerDutyChannel.send_alert()` execute concurrently.
7. Delivery outcomes persist to `AlertHistoryORM`.

---

## 16. Sequence Diagrams

```
EventBus -> AlertRuleEngine: on_event(domain_event)
activate AlertRuleEngine
AlertRuleEngine -> AlertRepo: fetch_active_rules(tenant_id, event_type)
AlertRepo --> AlertRuleEngine: matching_rules
loop for each rule
  AlertRuleEngine -> AlertRuleEngine: evaluate_condition(event.payload, rule)
  alt condition matches
    AlertRuleEngine -> DedupEngine: check_and_set_cooldown(rule.id, rule.cooldown_min)
    DedupEngine -> Redis: SETNX("cooldown:" + rule.id, "1", ttl)
    Redis --> DedupEngine: True (lock acquired)
    DedupEngine --> AlertRuleEngine: can_trigger=True
    AlertRuleEngine -> AlertDispatcher: dispatch_async(rule, event_payload)
    AlertDispatcher -> SlackChannel: send_alert(payload)
    AlertDispatcher -> PagerDutyChannel: send_alert(payload)
    SlackChannel --> AlertDispatcher: status=SUCCESS
    PagerDutyChannel --> AlertDispatcher: status=SUCCESS
    AlertDispatcher -> AlertRepo: save_history(history_orm)
  end
end
deactivate AlertRuleEngine
```

---

## 17. Folder Structure Changes

```
backend/modules/alerts/
├── __init__.py
├── api/
│   ├── __init__.py
│   └── routes.py                 # [NEW] REST endpoints
├── channels/
│   ├── __init__.py
│   ├── base.py                   # [NEW] Channel abstraction
│   ├── email_channel.py          # [NEW] SMTP delivery
│   ├── pagerduty_channel.py      # [NEW] PagerDuty delivery
│   ├── slack_channel.py          # [NEW] Slack Block Kit delivery
│   └── webhook_channel.py        # [NEW] Signed HTTPS webhook
├── models/
│   ├── __init__.py
│   ├── alert_history.py          # [NEW] ORM for dispatch records
│   └── alert_rule.py             # [NEW] ORM for tenant rules
├── repositories/
│   ├── __init__.py
│   └── alert_repository.py       # [NEW] Repository layer
├── schemas/
│   ├── __init__.py
│   ├── alert_dto.py              # [NEW] DTO contracts
│   └── errors.py                 # [NEW] Alerting exceptions
└── services/
    ├── __init__.py
    ├── deduplication.py          # [NEW] Redis cooldown engine
    ├── dispatcher.py             # [NEW] Multi-channel dispatcher
    └── rule_engine.py            # [NEW] Event rule evaluation
```

---

## 18. File Creation Plan

| File Path | Type | Justification / Purpose |
| :--- | :--- | :--- |
| `backend/modules/alerts/schemas/errors.py` | New | Defines `ChannelDeliveryError`, `RuleEvaluationError`. |
| `backend/modules/alerts/schemas/alert_dto.py` | New | Defines rule creation, history, and channel DTOs. |
| `backend/modules/alerts/channels/base.py` | New | Abstract base class `BaseNotificationChannel`. |
| `backend/modules/alerts/channels/slack_channel.py` | New | Slack Block Kit integration. |
| `backend/modules/alerts/channels/pagerduty_channel.py` | New | PagerDuty Events API v2 integration. |
| `backend/modules/alerts/channels/email_channel.py` | New | SMTP/SendGrid mailer. |
| `backend/modules/alerts/channels/webhook_channel.py` | New | Signed HMAC-SHA256 custom webhook client. |
| `backend/modules/alerts/services/deduplication.py` | New | Redis cooldown engine. |
| `backend/modules/alerts/services/dispatcher.py` | New | Celery task dispatcher and history logger. |
| `backend/modules/alerts/services/rule_engine.py` | New | Core condition evaluation engine. |
| `backend/modules/alerts/models/alert_rule.py` | New | ORM entity `AlertRuleORM`. |
| `backend/modules/alerts/models/alert_history.py` | New | ORM entity `AlertHistoryORM`. |
| `backend/modules/alerts/repositories/alert_repository.py` | New | Repository layer. |
| `backend/modules/alerts/api/routes.py` | New | FastAPI management endpoints (`/api/v1/alerts/*`). |
| `alembic/versions/0017_alerting_engine_schema.py` | New | Migration creating alert tables. |

---

## 19. Database Changes

### Table: `alert_rules`
| Column Name | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | UUID | PRIMARY KEY | Rule ID |
| `tenant_id` | VARCHAR(64) | NOT NULL, INDEX | Tenant namespace |
| `name` | VARCHAR(128) | NOT NULL | Rule display title |
| `metric_name` | VARCHAR(64) | NOT NULL | Monitored metric/field |
| `operator` | VARCHAR(32) | NOT NULL | `EQUALS`, `LESS_THAN`, `GREATER_THAN` |
| `threshold_value`| VARCHAR(128)| NOT NULL | Target trigger boundary |
| `channels_config`| JSONB | NOT NULL | List of target channels & URLs/keys |
| `cooldown_minutes`| INTEGER | NOT NULL | Cooldown window (default `15`) |
| `is_active` | BOOLEAN | NOT NULL | Rule enable toggle |

### Table: `alert_history`
| Column Name | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | UUID | PRIMARY KEY | Dispatch record ID |
| `rule_id` | UUID | FOREIGN KEY | Triggered rule |
| `tenant_id` | VARCHAR(64) | NOT NULL, INDEX | Tenant namespace |
| `channel_type` | VARCHAR(32) | NOT NULL | `SLACK`, `PAGERDUTY`, `WEBHOOK` |
| `status` | VARCHAR(32) | NOT NULL | `DELIVERED`, `FAILED`, `SUPPRESSED` |
| `payload_sent` | JSONB | NOT NULL | Formatted alert content |
| `error_message` | TEXT | NULL | HTTP error description if delivery failed |
| `triggered_at` | TIMESTAMP | NOT NULL | Dispatch timestamp |

---

## 20. API Design

| Method | Endpoint | Request Body | Response DTO | Summary |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/alerts/rules` | `AlertRuleCreateDTO` | `AlertRuleDTO` | Create a new tenant alert rule |
| `GET` | `/api/v1/alerts/rules` | N/A (`?tenant_id=...`) | `list[AlertRuleDTO]` | List all configured alert rules for a tenant |
| `PUT` | `/api/v1/alerts/rules/{id}` | `AlertRuleUpdateDTO` | `AlertRuleDTO` | Update or disable an alert rule |
| `GET` | `/api/v1/alerts/history` | N/A (`?page=1&size=20`) | `list[AlertHistoryDTO]` | Fetch paginated alert dispatch audit logs |

---

## 21. Configuration Changes

Add to `configs/app_config.py`:
* `ALERT_DEFAULT_COOLDOWN_MINUTES`: Default `15`.
* `ALERT_WEBHOOK_TIMEOUT_SEC`: Default `5`.
* `ALERT_MAX_RETRIES`: Default `3`.

---

## 22. Environment Variables

| Variable Name | Default | Description |
| :--- | :--- | :--- |
| `RAGUARD_ALERT_WEBHOOK_TIMEOUT` | `5` | Network timeout for outbound webhook requests |
| `RAGUARD_ALERT_SECRET_KEY` | `raguard-hmac-secret` | HMAC signing key for custom webhook payloads |
| `RAGUARD_ALERTS_ENABLED` | `true` | Master feature flag enabling notification engine |

---

## 23. Security Considerations

* **HMAC Payload Signing**: Outbound custom webhooks MUST include `X-RAGuard-Signature: t=timestamp,v1=sha256_hex_mac` computed over the JSON payload using `RAGUARD_ALERT_SECRET_KEY` to prevent webhook spoofing.
* **Secret Encryption**: Third-party webhook URLs and PagerDuty routing keys stored inside `AlertRuleORM.channels_config` must be encrypted at rest or redacted from API read endpoints.

---

## 24. Performance Considerations

* **Non-Blocking Network Dispatch**: Outbound HTTP calls to Slack/PagerDuty MUST run within asynchronous Celery workers (`dispatch_alert_task`) with `httpx.AsyncClient(timeout=5.0)` to ensure never blocking the `EventDispatcher`.
* **Redis Cooldown Atomic Check**: Deduplication checks MUST use atomic `SETNX` operations (`redis.set(key, "1", ex=ttl, nx=True)`) to eliminate race conditions under concurrent worker executions.

---

## 25. Monitoring Strategy

* **OpenTelemetry Tracing**: Record span `raguard.alerts.dispatch` with attributes `channel_type`, `rule_id`, `delivery_status`.
* **Prometheus Metrics**:
  * `raguard_alerts_triggered_total{tenant_id, rule_name}`
  * `raguard_alerts_delivered_total{channel_type, status}`
  * `raguard_alerts_suppressed_total{tenant_id, reason="cooldown"}`

---

## 26. Error Handling Strategy

* Raise `ChannelDeliveryError` if third-party HTTP endpoint returns $4xx / 5xx$ status codes.
* If channel delivery fails, `AlertDispatcher` retries up to `3 times` via Celery exponential backoff before marking record `status = FAILED` in `alert_history`.

---

## 27. Testing Strategy

* **Unit Tests**: Mock `httpx.AsyncClient` responses to test `SlackChannel` and `PagerDutyChannel` formatting; test `AlertRuleEngine` condition parsing across boundary numbers.
* **Integration Tests**: Verify end-to-end event bus publication triggering Redis `SETNX` cooldown creation and database insertion into `alert_history`.
* **Regression Tests**: Verify that high-volume event publishing does not increase memory footprint or slow down main API response paths.

---

## 28. Unit Testing Plan

* `tests/unit/backend/modules/alerts/test_rule_engine.py`: Test operators (`EQUALS`, `LESS_THAN`, `GREATER_THAN`) across DTO payloads.
* `tests/unit/backend/modules/alerts/test_deduplication.py`: Test Redis TTL calculation and cooldown suppression logic.
* `tests/unit/backend/modules/alerts/test_channels.py`: Test Slack Block Kit JSON structure and `WebhookChannel` HMAC signature generation.

---

## 29. Integration Testing Plan

* `tests/integration/test_alert_routes.py`: Verify CRUD API rules (`POST /api/v1/alerts/rules`) and tenant isolation verification.
* `tests/integration/test_alert_dispatcher.py`: Verify Celery task invocation and `AlertHistoryORM` persistence upon event dispatch.

---

## 30. Risk Assessment

| Risk | Likelihood | Impact | Mitigation Strategy |
| :--- | :--- | :--- | :--- |
| External channel webhook endpoint down causing task queue buildup | Medium | Medium | Enforce strict `5.0s` HTTP timeouts and cap maximum Celery task retries to `3`. |
| Misconfigured rule (`final_score < 100.0`) triggering continuous alerts | High | Medium | Enforce mandatory `cooldown_minutes >= 5` on all rules created via API. |

---

## 31. Acceptance Criteria

1. `AlertRuleEngine` correctly intercepts events matching rule criteria and triggers background delivery tasks.
2. `AlertDeduplicationEngine` suppresses $100\%$ of duplicate alerts fired for the same rule during the active Redis cooldown window.
3. Outbound `WebhookChannel` payloads contain cryptographically valid `X-RAGuard-Signature` headers verifying authenticity.

---

## 32. Completion Criteria

* All code committed inside `backend/modules/alerts/`.
* Alembic migration `0017_alerting_engine_schema.py` applied.
* 100% of Phase 17 unit and integration tests passing alongside all Phase 0–16 tests.

---

## 33. Milestone Breakdown

* **Milestone 1 (`impl_m17_part1.py`)**: DTOs (`alert_dto.py`), provider base (`channels/base.py`), ORM models, and migration `0017_alerting_engine_schema.py`.
* **Milestone 2 (`impl_m17_part2.py`)**: Implement `SlackChannel`, `PagerDutyChannel`, `WebhookChannel`, and `EmailChannel`.
* **Milestone 3 (`impl_m17_part3.py`)**: Implement `AlertRuleEngine`, `AlertDeduplicationEngine`, `AlertDispatcher`, and REST API (`api/routes.py`).
* **Milestone 4 (`impl_m17_tests.py`)**: Execute unit (`test_rule_engine.py`, `test_channels.py`) and integration tests.

---

## 34. Provider Abstraction

All notification destinations implement `BaseNotificationChannel` (`backend/modules/alerts/channels/base.py`), ensuring clean isolation of channel formatting logic from core event evaluation.

---

## 35. Architecture Decision Records (ADR)

* **ADR-017-1**: Enforce Redis atomic `SETNX` cooldown locks (`raguard:alert:cooldown:{rule_id}`) prior to task dispatch to guarantee zero alert duplication in multi-replica environments.
* **ADR-017-2**: Sign all outbound custom webhooks with HMAC-SHA256 (`X-RAGuard-Signature`) to comply with zero-trust enterprise security standards.

---

## 36. Versioning Strategy

All management endpoints and payload schemas use API `v1` (`AlertRuleCreateDTO`, `AlertPayloadDTO`), ensuring consistent JSON formatting across channels.

---

## 37. Feature Flags

`RAGUARD_ALERTS_ENABLED`: If set to `false`, `AlertRuleEngine.on_event()` immediately returns without processing, bypassing all evaluations and outbound network traffic.

---

## 38. Performance Budgets

* Rule evaluation per event: `< 2ms`.
* Redis cooldown check: `< 1ms`.
* Outbound webhook network timeout: `5000ms` (executed via background Celery task).

---

## 39. Deployment Architecture

`AlertRuleEngine` runs inside backend containers listening to the in-memory/Redis `EventDispatcher`. Outbound delivery runs inside Celery worker containers (`celery worker -Q notifications`).

---

## 40. Failure Recovery Matrix

| Failure Scenario | Detection Mechanism | Recovery Behavior |
| :--- | :--- | :--- |
| Outbound Webhook HTTP 503 | `httpx.HTTPStatusError` | Celery task retries up to `3 times` with exponential backoff before logging `status = FAILED`. |
| Redis Down During Cooldown Check | `RedisConnectionError` | Log warning, allow alert dispatch once (`fail-open`) rather than losing critical security alerts. |

---

## 41. Dependency Graph

```
Phases 11, 12, 13, 14 ──► EventDispatcher ──► Phase 17 (AlertRuleEngine & Channels)
                                                            │
                                                            ▼
                                        Slack / PagerDuty / Signed Webhooks
```

---

## 42. Rollback Strategy

Set `RAGUARD_ALERTS_ENABLED=false` to silence all alerting instantly. Run `alembic downgrade 0016` to remove `alert_rules` and `alert_history` cleanly.

---

## 43. Success Metrics

* **Incident Dispatch Latency**: Mean time from anomaly event detection to webhook delivery $< 1.5\text{s}$.
* **Suppression Accuracy**: $100\%$ prevention of duplicate notifications during cooldown windows.
* **Webhook Reliability**: $> 99.8\%$ delivery success rate across healthy target endpoints.

---

## 44. Traceability Matrix

| Requirement | PRD Reference | Architecture Document | Implementing Class |
| :--- | :--- | :--- | :--- |
| Multi-Channel Notifications | Section 7.2 | `AI_ARCHITECTURE_AFTER_IMPROVEMENTS.md` | `SlackChannel`, `PagerDutyChannel` |
| Alert Rule Evaluation | Section 7.2 | `ARCHITECTURE_AFTER_IMPROVEMENTS.md` | `AlertRuleEngine` |
| Cooldown Deduplication | Section 7.2 | `EVALUATION_FRAMEWORK_AFTER_IMPROVEMENTS.md` | `AlertDeduplicationEngine` |

---

## 45. Implementation Checklist

- [ ] Create `schemas/errors.py` and `schemas/alert_dto.py`.
- [ ] Create `channels/base.py`, `channels/slack_channel.py`, `channels/pagerduty_channel.py`, `channels/webhook_channel.py`, and `channels/email_channel.py`.
- [ ] Create `services/deduplication.py`, `services/dispatcher.py`, and `services/rule_engine.py`.
- [ ] Create `models/alert_rule.py`, `models/alert_history.py`, `repositories/alert_repository.py`, and `api/routes.py`.
- [ ] Create migration `0017_alerting_engine_schema.py`.

---

## 46. Phase Completion Checklist

- [ ] All 4 implementation milestones (`impl_m17_*.py`) executed cleanly.
- [ ] 100% of Phase 17 unit and integration tests passing (`test_alert_*.py`).
- [ ] Zero static analysis errors (`mypy`, `ruff`).
- [ ] No regressions across Phase 0–16 test suites.

---

## 47. File Inventory

* **New Files**:
  * `backend/modules/alerts/__init__.py`
  * `backend/modules/alerts/schemas/__init__.py`
  * `backend/modules/alerts/schemas/errors.py`
  * `backend/modules/alerts/schemas/alert_dto.py`
  * `backend/modules/alerts/channels/__init__.py`
  * `backend/modules/alerts/channels/base.py`
  * `backend/modules/alerts/channels/slack_channel.py`
  * `backend/modules/alerts/channels/pagerduty_channel.py`
  * `backend/modules/alerts/channels/email_channel.py`
  * `backend/modules/alerts/channels/webhook_channel.py`
  * `backend/modules/alerts/services/__init__.py`
  * `backend/modules/alerts/services/deduplication.py`
  * `backend/modules/alerts/services/dispatcher.py`
  * `backend/modules/alerts/services/rule_engine.py`
  * `backend/modules/alerts/models/__init__.py`
  * `backend/modules/alerts/models/alert_rule.py`
  * `backend/modules/alerts/models/alert_history.py`
  * `backend/modules/alerts/repositories/__init__.py`
  * `backend/modules/alerts/repositories/alert_repository.py`
  * `backend/modules/alerts/api/__init__.py`
  * `backend/modules/alerts/api/routes.py`
  * `alembic/versions/0017_alerting_engine_schema.py`
  * `tests/unit/backend/modules/alerts/test_rule_engine.py`
  * `tests/unit/backend/modules/alerts/test_deduplication.py`
  * `tests/unit/backend/modules/alerts/test_channels.py`
  * `tests/integration/test_alert_routes.py`
  * `tests/integration/test_alert_dispatcher.py`

---

## 48. Cross-Phase Consistency Review

Phase 17 consumes identical event payloads (`ReliabilityScoreComputedEvent`, `HallucinationInterceptedEvent`) emitted by Phase 11 (`reflection`), Phase 12 (`validation`), and Phase 13 (`scoring`), while outputting audit logs visible directly inside Phase 16 (`dashboard`).

---

## 49. Enterprise Design Review Summary

* **SOLID**: Channel formatting (`SlackChannel`) is strictly decoupled from condition matching (`AlertRuleEngine`) and deduplication (`AlertDeduplicationEngine`).
* **Clean Architecture**: Outbound HTTP network providers operate behind clean async interfaces (`BaseNotificationChannel`).
* **Performance**: Redis atomic locks and Celery async workers ensure zero blocking on main event bus publication.

---

## 50. Final Deliverables Summary

* **Folder Structure**: Build out `api/`, `channels/`, `models/`, `repositories/`, `schemas/`, `services/` inside `backend/modules/alerts/`.
* **Database**: Migration `0017_alerting_engine_schema.py` creating `alert_rules` and `alert_history`.
* **API Inventory**: `POST /api/v1/alerts/rules`, `GET /api/v1/alerts/rules`, `PUT /api/v1/alerts/rules/{id}`, `GET /api/v1/alerts/history`.
* **Milestone Scripts**: `impl_m17_part1.py`, `impl_m17_part2.py`, `impl_m17_part3.py`, `impl_m17_tests.py`.
