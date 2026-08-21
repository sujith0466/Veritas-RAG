# Chaos Engineering & Resilience Runbook (F15.3)

**Target Audience:** Reliability Engineers, SRE On-Call, QA
**System:** RAGuard V2 Multi-Tenant AI Platform
**Classification:** Resilience Verification Framework
**Status:** PRODUCTION READY

---

## 1. Overview & Blast-Radius Governance

Chaos experiments intentionally inject controlled hardware, network, and upstream service faults in a dedicated staging environment to validate self-healing capabilities, alert firing, circuit breaker trip times, and graceful degradation.

### Blast-Radius Rules
1. **Never in Production**: `ChaosInjector` includes a hardcoded runtime guard: `if self.is_production: return`.
2. **Time-To-Live (TTL)**: All active chaos policies auto-expire after 10 minutes (`fault_policies.expires_at`).
3. **Emergency Abort**: Any experiment that causes irreversible datastore corruption or hangs active worker pools MUST be aborted immediately:
   ```bash
   # Emergency chaos policy purge
   psql -U raguard -d raguard_db -c "UPDATE fault_policies SET is_active = false;"
   ```

---

## 2. Chaos Experiment Matrix (C1 – C8)

| Experiment ID | Hypothesis & Target | Injection Method | Expected System Behavior | Observability Signals | Abort Criteria |
|:---|:---|:---|:---|:---|:---|
| **C1: API Pod Failure** | K8s restarts dead FastAPI pods within 30s with zero transaction loss | `kubectl delete pod -n raguard-staging -l app.kubernetes.io/name=raguard` | Liveness/Readiness probes fail briefly; replica auto-heals; load balancer reroutes traffic | `ServiceUnavailable` alert; container restart counter | Pod CrashLoopBackOff > 3 restarts |
| **C2: Redis Cache Failure** | System degrades gracefully without crashing when Redis fails | `docker stop raguard-redis` | `QuotaGovernor` falls back to direct PostgreSQL reads; session cache falls back to DB | `LowCacheHitRatio` alert; error logs with PG fallback info | Elevated DB pool saturation > 90% |
| **C3: Database / PgBouncer Failure** | Pool exhaustion trips circuit breaker and returns HTTP 503 rather than hung connections | Inject connection pool exhaustion script | Requests timeout gracefully; returns structured 503 error; pool recovers when load decreases | `CriticalAPIErrorRate` alert; DB pool saturation metric | Postgres process termination |
| **C4: Qdrant Vector DB Drop** | Vector store disconnect trips circuit breaker without crashing API | `x-raguard-chaos-token: test-qdrant-drop` (`QDRANT_DISCONNECT`) | RAG search returns graceful degraded response; circuit breaker trips to OPEN | `QdrantVectorDBUnavailable` alert; `CircuitBreakerTripped` alert | API process unhandled fatal exception |
| **C5: Object Storage Outage** | MinIO downtime isolates document uploads without breaking chat/retrieval | `docker stop raguard-minio` | Document upload returns HTTP 503; active chat using existing embeddings continues | `ObjectStorageHighFailureRate` alert | Ingestion worker crash loop |
| **C6: Celery Worker Failure** | Worker termination does not drop in-flight jobs; DLQ requeues unacknowledged tasks | `docker stop raguard-celery-worker` | In-flight jobs redelivered upon worker restart; no document permanently stuck in `PROCESSING` | `CeleryQueueBacklog` alert | Message loss in Redis broker |
| **C7: LLM Primary Outage** | Primary LLM 503 triggers failover to secondary provider or trips circuit breaker | `x-raguard-chaos-token: test-llm-outage` (`LLM_HTTP_503`) | Fallback provider invoked transparently; if all fail, user receives contextual error | `CircuitBreakerTripped` alert | Request hang exceeding 30s timeout |
| **C8: Fallback Provider Exhaustion** | Exhaustion of all LLM providers cleanly degrades with descriptive error | Inject multi-provider failure policy | Returns HTTP 503 with retry-after; circuit breaker records failures | `CircuitBreakerTripped` alert (SEV-1) | Unhandled 500 internal server error |

---

## 3. Step-by-Step Staging Chaos Execution

### 3.1 Injecting Application-Layer Faults
```bash
# 1. Insert a fault policy into the database
psql -U raguard -d raguard_db -c "
INSERT INTO fault_policies (id, chaos_token, fault_type, error_rate_pct, is_active, expires_at)
VALUES (gen_random_uuid(), 'test-llm-outage', 'LLM_HTTP_503', 1.0, true, NOW() + INTERVAL '5 minutes');"

# 2. Issue request with chaos header
curl -H "x-raguard-chaos-token: test-llm-outage" http://localhost:8000/api/v1/chat/stream -d '{"message": "hello"}'

# 3. Verify error handling and alert generation in Prometheus
```

### 3.2 Kubernetes Pod Kill Drill (Staging Only)
```bash
# Kill random API pod in staging
kubectl delete pod -n raguard-staging -l app.kubernetes.io/name=raguard --wait=false

# Monitor recovery and probe status
kubectl get pods -n raguard-staging -w
```
