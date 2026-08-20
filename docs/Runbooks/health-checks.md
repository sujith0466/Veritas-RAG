# Health Checks & Probes Runbook

**Target Components:** Kubernetes Ingress, Load Balancers, Prometheus Scraper, SRE On-Call.

---

## 1. Kubernetes Probe Specifications

| Probe | Endpoint Path | Method | Expected HTTP Code | Frequency | Timeout | Description |
|---|---|---|---|---|---|---|
| **Liveness** | `/health/live` | `GET` | 200 OK | 10s | 2s | Validates FastAPI ASGI event loop is active and not deadlocked. |
| **Readiness** | `/health/ready` | `GET` | 200 OK | 10s | 5s | Validates database, Redis, Qdrant, and storage dependencies. Returns 503 if any core dependency fails. |
| **Startup** | `/health/startup` | `GET` | 200 OK | 5s | 5s | Blocks incoming traffic until database migrations and initialization routines are complete. |
| **Detailed** | `/health/detailed` | `GET` | 200 OK | On-Demand | 10s | Authenticated endpoint (requires `PLATFORM_ADMIN` JWT) returning granular per-dependency latency measurements. |

---

## 2. Triage & Incident Resolution

### 2.1 Readiness Probe Failing (503 Service Unavailable)
1. Check endpoint payload: `curl -s http://localhost:8000/health/ready | jq .`
2. Identify failing dependency in `dependencies` dictionary (`postgresql`, `redis`, `qdrant`, `object_storage`).
3. For PostgreSQL failure: Inspect connection pool exhaustion or database lock contentions.
4. For Qdrant failure: Inspect `raguard-qdrant` container logs and memory allocation (`docker logs raguard-qdrant-1`).
5. For Redis failure: Verify Redis memory usage and cluster ping latency (`redis-cli ping`).

### 2.2 Startup Probe Failing (503 Service Unavailable)
1. Check migration state: `docker logs raguard-api-1 | grep "migration"`
2. Verify Alembic migration completion: `alembic current`
3. Check database connectivity during application initialization.
