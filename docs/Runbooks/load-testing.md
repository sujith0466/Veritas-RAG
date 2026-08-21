# Load Testing & Performance Validation Runbook (F15.2)

**Target Audience:** Performance Engineers, QA, SRE On-Call
**System:** Veritas RAG — An Enterprise Knowledge Reliability Platform for Self-Correcting Retrieval-Augmented Generation
**Classification:** Performance & Scalability Standard
**Status:** PRODUCTION READY

---

## 1. Overview & Tooling

Veritas RAG validates system throughput, concurrency limits, and database atomicity under load using **k6 OSS** against a dedicated staging environment.

### Target Performance SLOs

| Workload / Endpoint | Concurrency Target | P95 Latency SLO | P99 Latency SLO | Error Rate Threshold |
|:---|:---|:---|:---|:---|
| **Auth & Sessions** (`/api/v1/auth/*`) | 100 VUs | ≤ 400ms | ≤ 800ms | < 0.5% |
| **Workspace CRUD** (`/api/v1/workspaces/*`) | 100 VUs | ≤ 300ms | ≤ 600ms | < 0.5% |
| **Chat SSE First-Token** (`/api/v1/chat/stream`) | 50 Concurrent Streams | ≤ 3.0s | ≤ 5.0s | < 1.0% |
| **Document Upload** (1MB PDF) | 50 VUs | ≤ 5.0s | ≤ 10.0s | < 1.0% |
| **Admin Aggregation** (`/api/v1/platform-admin/*`) | 5 VUs | ≤ 2.0s | ≤ 4.0s | < 1.0% |

---

## 2. Mandatory Test Scenario: Concurrent Quota Increment Atomicity

### Purpose
To prove that F13.2's PostgreSQL `ON CONFLICT (workspace_id, billing_period_start) DO UPDATE` atomic UPSERT in `UsageRepository` correctly accumulates tokens under high concurrency without lost updates or race conditions.

### Test Execution
```bash
# 1. Ensure staging database is seeded with a test workspace
WORKSPACE_ID="00000000-0000-0000-0000-000000000001"

# 2. Record initial token count
INITIAL_TOKENS=$(psql -h localhost -U raguard -d raguard_db -t -c \
    "SELECT used_tokens FROM workspace_usages WHERE workspace_id = '$WORKSPACE_ID' AND billing_period_start = CURRENT_DATE;")
INITIAL_TOKENS=${INITIAL_TOKENS:-0}

# 3. Fire 100 concurrent requests each consuming exactly 100 tokens
k6 run --vus 100 --iterations 100 k6/scenarios/quota_concurrent_increment.js

# 4. Verify post-test accumulated tokens
FINAL_TOKENS=$(psql -h localhost -U raguard -d raguard_db -t -c \
    "SELECT used_tokens FROM workspace_usages WHERE workspace_id = '$WORKSPACE_ID' AND billing_period_start = CURRENT_DATE;")

# Expected equation: FINAL_TOKENS == INITIAL_TOKENS + (100 * successful_requests)
```

---

## 3. Standard k6 Execution Suite

```bash
# Execute entire load testing suite
bash k6/run_all.sh

# Or execute individual scenario:
k6 run --vus 50 --duration 5m k6/scenarios/chat_streaming.js
```

---

## 4. Monitoring & Abort Thresholds

During load test execution, monitor the following panels in Grafana:
- **Connection Pool Saturation**: If PostgreSQL connections reach > 90% of `pool_size`, abort.
- **CPU / Memory Saturation**: If API pod CPU > 85%, trigger horizontal autoscaling (HPA).
- **Error Burst**: If 5xx error rate exceeds 5%, immediately abort the test.
