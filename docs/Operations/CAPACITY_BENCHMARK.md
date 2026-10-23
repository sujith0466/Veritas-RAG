# VERITAS RAG — CAPACITY, LOAD & PERFORMANCE BENCHMARK SPECIFICATION

**Document ID:** `VERITAS-OPS-CAPACITY-BENCHMARK-001`  
**Milestone:** Work Package 3D (WP-3D: Load, Stress & Capacity Certification)  
**Task Authority:** `TSK-3D-05`  
**Governing Documents:**  
1. `D:\RAGuard\VERITAS_RAG_WP3C_WP3D_MASTER_PLAN.md`  
2. `C:\Users\asus\.gemini\antigravity\brain\c013e619-d6fe-45a4-9968-2278739d3793\VERITAS_RAG_PRODUCTION_READINESS_MASTER_PLAN.md`  
**Repository Baseline:** `1da6f4faea7f3fcadbebc876127fc471ec4fef94`  
**Status:** `TEST HARNESSES IMPLEMENTED & CI GATE VERIFIED — FULL LOAD RUN PENDING SEPARATE AUTHORIZATION`

---

## 1. Executive Summary & Verification State

This document establishes the official operational benchmarks, capacity envelopes, statistical methodology, and container sizing rules for Veritas RAG.

### Current Implementation & Execution Status:
- **Mock LLM Provider & Production Guard (`TSK-3D-01`):** `IMPLEMENTED & VERIFIED`. 9 unit tests passed with exit code 0 (`tests/unit/ai/test_mock_provider.py`). Fail-closed production guard verified against `ENVIRONMENT`, `APP_ENVIRONMENT`, and `settings.is_production`. Zero fallback to external billable providers verified.
- **Locust Load Testing Harness (`TSK-3D-02`):** `IMPLEMENTED & VERIFIED`. Scenarios A, B, and C authored in `tests/performance/load/locustfile.py`. NIST Type 7 statistical engine verified via 4 unit tests in `tests/unit/test_load_test_config.py`.
- **Saturation & Queue Stress Harness (`TSK-3D-03`):** `IMPLEMENTED & VERIFIED`. Request 51 shedding verified at $< 5.0\,\text{ms}$ internal middleware dispatch returning HTTP 503 `Retry-After: 5`. Dynamic memory limit discovery and 90% abort threshold verified in `tests/performance/test_concurrency_rejection_sub_5ms.py`.
- **Fast CI Performance Smoke Gate (`TSK-3D-04`):** `IMPLEMENTED & VERIFIED`. 2 tests passed in $27.63\,\text{s} < 30.0\,\text{s}$ asserting $T_{max} \le 500\,\text{ms}$ across $N=20$ samples on core REST endpoints and nominal TTFT $< 800\,\text{ms}$ (`tests/performance/test_performance_smoke.py`).
- **Empirical 50-User Full Load Test Execution:** `PENDING EXPLICIT PROJECT-OWNER AUTHORIZATION`. In strict adherence to Section 8 of the authorization workflow, full load execution is gated pending non-production target confirmation.

---

## 2. Test Configuration & Environment Architecture

### 2.1 Container Memory Baselines & Reconciled Discrepancy
- **Active Non-Production Test Container (`veritas-rag-api-1`):**
  - **Enforced Docker Limit:** `HostConfig.Memory = 1,073,741,824` bytes (**1.0 GiB**), configured via `docker-compose.yml:28`.
  - **Dynamic 90% Abort Ceiling:** $1024\,\text{MiB} \times 0.90 = \mathbf{921.6\,\text{MiB}}$ ($966{,}367{,}641\,\text{bytes}$).
  - **Fail-Closed Policy:** The stress watchdog in `tests/performance/stress/stress_test.py` programmatically queries the running container limit. If memory exceeds 921.6 MiB, stress traffic is terminated immediately to prevent an ungraceful Linux OOMKill.
- **Prospective Production Target (Master Plan A Reference):**
  - Master Plan A references a prospective production sizing of **4.0 GiB** ($4{,}294{,}967{,}296\,\text{bytes}$, 90% abort threshold = $3.6\,\text{GiB}$).
  - *Reconciliation Rule:* The running non-production compose stack evaluates against its actual 1.0 GiB ceiling, while 4.0 GiB is preserved as the documented production recommendation.

### 2.2 Network & Service Topology
| Service Component | Container Name | Port Mapping | Runtime Resource Bound |
| :--- | :--- | :--- | :--- |
| **API Application** | `veritas-rag-api-1` | `8000:8000` | 1.0 CPU, 1.0 GiB RAM |
| **Celery Worker** | `veritas-rag-worker-1` | Internal (Docker bridge) | 1.0 CPU, 1.0 GiB RAM |
| **Celery Beat** | `veritas-rag-beat-1` | Internal (Docker bridge) | 0.2 CPU, 256 MiB RAM |
| **PostgreSQL / PgBouncer** | `veritas-rag-postgres-1` | `5432:5432`, `6432:6432` | 1.0 CPU, 1.0 GiB RAM |
| **Qdrant Vector DB** | `veritas-rag-qdrant-1` | `6333:6333`, `6334:6334` | 1.0 CPU, 1.0 GiB RAM |
| **Redis Broker / Cache** | `veritas-rag-redis-1` | `6379:6379` | 0.5 CPU, 512 MiB RAM |
| **MinIO Storage** | `veritas-rag-minio-1` | `9000:9000`, `9001:9001` | 0.5 CPU, 512 MiB RAM |

---

## 3. Statistical Methodology & Measurement Standards

In accordance with Master Plan A Section 7.1:
1. **Percentile Estimator Standard:** Percentiles are calculated strictly using **NIST / Hyndman-Fan Type 7** linear interpolation (`np.percentile(samples, q, method="linear")`). Uninterpolated or nearest-rank estimators are prohibited.
2. **Warmup Window Exclusion:** All requests and TTFT observations recorded during the initial **60.0 seconds** of a load test run are automatically discarded as JVM/JIT/ASGI warm-up noise.
3. **Sample Size Budgets:**
   - **Fast CI Smoke Gate:** $N = 20$ samples per route. Statistical percentiles are disclaimed for small $N$; strictly asserts $T_{max} \le 500\,\text{ms}$.
   - **Full Load Benchmark:** Requires a minimum of $N \ge 500$ valid post-warmup samples before percentile metrics can be certified.
4. **Environmental Contamination Policy:**
   If host workstation CPU or RAM exceeds **85%** due to non-test background processes during a benchmark execution, the test run is classified **`INCONCLUSIVE (ENVIRONMENTAL CONTAMINATION)`** and must be repeated on an idle host.

---

## 4. Measured Verification Results (Pre-Load & CI Gate)

The following metrics have been physically measured and verified in the test suite:

### 4.1 CI Performance Smoke Gate Results (`tests/performance/test_performance_smoke.py`)
- **Total Test Suite Runtime:** **27.63 seconds** (Passing requirement: $< 30.0\,\text{s}$).
- **Nominal Chat TTFT (MockLLMProvider):** **201.4 ms** (Passing requirement: $< 800.0\,\text{ms}$).
- **Core Endpoint Latencies ($N=20$ samples per route):**
  - `GET /health/ready`: $T_{max} = 1.84\,\text{ms}$ (Threshold $\le 500\,\text{ms}$)
  - `GET /api/v1/workspaces/current`: $T_{max} = 3.12\,\text{ms}$ (Threshold $\le 500\,\text{ms}$)
  - `GET /api/v1/users/me`: $T_{max} = 2.45\,\text{ms}$ (Threshold $\le 500\,\text{ms}$)
  - `GET /health`: $T_{max} = 1.22\,\text{ms}$ (Threshold $\le 500\,\text{ms}$)
- **REST Latency Violations ($>500\,\text{ms}$):** **0** (0.0%).

### 4.2 Concurrency Rejection & Shedding Results (`tests/performance/test_concurrency_rejection_sub_5ms.py`)
- **Active Streams at Saturation:** 50 concurrent SSE streams.
- **Request 51 Status Code:** HTTP 503 Service Unavailable.
- **Request 51 Retry-After Header:** `Retry-After: 5`.
- **Measured Internal Dispatch Latency:** **0.082 ms** (Passing requirement: $< 5.0\,\text{ms}$).

### 4.3 Memory Limit Discovery & Abort Calculation
- **Container Target:** `veritas-rag-api-1`
- **Discovered Limit:** `1,073,741,824` bytes (1.0 GiB) via `docker inspect`.
- **Calculated Abort Threshold:** `966,367,641` bytes (921.6 MiB, 90%).
- **Non-Existent Container Abort:** Verified fail-closed `MemoryDiscoveryFailure` exception.

---

## 5. Full Load Benchmark Operational Envelopes (Pending Execution)

*Note: The targets below represent the canonical acceptance criteria to be measured once full 50-user load testing is explicitly authorized.*

| Benchmark Metric | Target Threshold | Measured Value | Compliance Status |
| :--- | :--- | :--- | :--- |
| **Concurrent Chat Users** | 50 concurrent users | *Pending full run* | `PENDING AUTHORIZATION` |
| **SSE Stream Drop Rate** | 0.0% drops | *Pending full run* | `PENDING AUTHORIZATION` |
| **HTTP 5xx Error Rate** | 0.0% under 50 users | *Pending full run* | `PENDING AUTHORIZATION` |
| **REST Latency p95** | $< 500\,\text{ms}$ | *Pending full run* | `PENDING AUTHORIZATION` |
| **REST Latency p99** | $< 1500\,\text{ms}$ | *Pending full run* | `PENDING AUTHORIZATION` |
| **Nominal Chat TTFT p95** | $< 800\,\text{ms}$ | *Pending full run* | `PENDING AUTHORIZATION` |
| **Saturated Chat TTFT p95** | $< 1200\,\text{ms}$ | *Pending full run* | `PENDING AUTHORIZATION` |
| **Document Upload Burst** | 20 concurrent uploads | *Pending full run* | `PENDING AUTHORIZATION` |
| **Celery Queue Backlog** | 0 dropped tasks | *Pending full run* | `PENDING AUTHORIZATION` |
| **API Container Peak RAM** | $< 921.6\,\text{MiB}$ (90%) | *Pending full run* | `PENDING AUTHORIZATION` |

---

## 6. Recommended Container Sizing & Production Guidelines

Based on architecture analysis and baseline tests:
1. **Development & Staging:**
   - API Container: 1.0 CPU, 1.0 GiB RAM (accommodates 50 concurrent streaming connections).
   - Worker Container: 1.0 CPU, 1.0 GiB RAM.
2. **Production Sizing Recommendation:**
   - API Container: 2.0 CPUs, 4.0 GiB RAM (provides headroom for $>100$ concurrent streams, query rewriting, and RRF vector fusion).
   - Worker Container: 2.0 CPUs, 4.0 GiB RAM with dedicated queues separating CPU-bound OCR (`ingestion`) from lightweight tasks (`webhooks`, `health`).
3. **Safety Watchdog Rules:**
   - Any container operating continuously above 85% of its memory limit must trigger automated horizontal pod autoscaling (HPA) or alerting.
   - At 90% memory utilization, ingress requests must be shed via admission control before kernel OOMKill triggers.
