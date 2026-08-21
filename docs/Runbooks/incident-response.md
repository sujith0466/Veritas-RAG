# Incident Response Runbook

**Target Audience:** SRE Incident Commanders, On-Call Engineers, Security Operations
**System:** Veritas RAG — An Enterprise Knowledge Reliability Platform for Self-Correcting Retrieval-Augmented Generation
**Classification:** Primary Operational Response Framework
**Status:** PRODUCTION READY

---

## 1. Severity Classification & Response SLA

| Severity | Definition | Initial Response SLA | Escalation Target | Communication Cadence |
|:---|:---|:---|:---|:---|
| **SEV-1 (Critical)** | Core outage, complete API downtime, vector database drop, or active security breach | **Immediate (< 5 mins)** | Incident Commander, VP Engineering, Security Lead | Updates every 15 mins in `#incident-war-room` |
| **SEV-2 (Major)** | Degradation in RAG generation, elevated P95 latency > 3s, single tenant impact, or queue delays | **< 15 mins** | Secondary On-Call, Component Lead | Updates every 30 mins |
| **SEV-3 (Minor)** | Non-critical background task failures, low cache hit ratio, or minor UI cosmetic issue | **< 2 Hours** | Engineering Backlog / Daily Triage | Updates in daily engineering sync |

---

## 2. Alert Triage Matrix

| Alert Name | Severity | Escalation | First Responder Action |
|:---|:---|:---|:---|
| `ServiceUnavailable` | **SEV-1** | PagerDuty | 1. Check pod status: `kubectl get pods -n raguard-production`<br>2. Inspect container logs for OOM or crash loops: `kubectl logs deployment/raguard-api`<br>3. Restart failing backend replicas or rollback if related to recent deployment. |
| `CriticalAPIErrorRate` | **SEV-1** | PagerDuty | 1. Open Grafana HTTP 5xx breakdown panel.<br>2. Trace correlation IDs in Loki: `{app="raguard"} \|= "ERROR"`.<br>3. Enable fallback circuit breaker if upstream LLM is failing. |
| `QdrantVectorDBUnavailable` | **SEV-1** | PagerDuty | 1. Check Qdrant cluster health (`curl http://raguard-qdrant:6333/healthz`).<br>2. Check host memory allocation (`kubectl top pod -l app.kubernetes.io/component=vector-db`).<br>3. Restart Qdrant service or recover snapshot. |
| `CircuitBreakerTripped` | **SEV-1** | PagerDuty | 1. Inspect upstream provider rate limits or vendor outage.<br>2. Failover to secondary LLM provider model or increase backoff multiplier. |
| `HighAPIRequestLatency` | **SEV-2** | 15m Escalation | 1. Inspect P95 latency breakdown panel in Grafana.<br>2. Check for database query locks or slow dense vector similarity searches. |
| `ObjectStorageHighFailureRate` | **SEV-2** | 15m Escalation | 1. Verify MinIO / S3 credentials and endpoint connectivity.<br>2. Check storage volume capacity on PVCs. |
| `CeleryQueueBacklog` | **SEV-2** | 15m Escalation | 1. Scale background workers: `kubectl scale deployment/raguard-celery-worker --replicas=5`.<br>2. Check for poisoned job in DLQ. |
| `LowCacheHitRatio` | **SEV-3** | Daily Triage | 1. Inspect Redis memory and key eviction policy.<br>2. Verify quota cache invalidation frequency. |

---

## 3. Incident Management Workflow

```
[1. Alert Triggered / Detected]
        │
[2. Acknowledge Alert in PagerDuty (SRE On-Call)]
        │
[3. Assess Severity: SEV-1 vs SEV-2 vs SEV-3]
        ├── If SEV-1: Open Incident Channel #incident-YYYYMMDD and summon Incident Commander
        │
[4. Triage & Root Cause Identification (Loki / OpenTelemetry Tracing / Grafana)]
        │
[5. Containment Action (Rollback, Scale Replicas, Enable Circuit Breaker)]
        │
[6. Service Recovery & Verification (/health/ready returns 200)]
        │
[7. Incident Closure & Post-Mortem (Within 48 Hours)]
```

---

## 4. Security Incident Response Procedures

### 4.1 Compromised LLM / Provider API Key
1. **Revoke**: Immediately revoke the exposed API key in the provider console (OpenAI / Gemini / Anthropic).
2. **Rotate**: Generate a replacement key and inject into Secret Manager / Kubernetes Secrets:
   ```bash
   kubectl create secret generic raguard-secrets --from-literal=OPENAI_API_KEY="new-key" --dry-run=client -o yaml | kubectl apply -f -
   ```
3. **Restart**: Trigger a rolling restart: `kubectl rollout restart deployment/raguard-api`.
4. **Audit**: Review `audit_logs` table and structured JSON logs for unauthorized prompt executions during the exposure window.

### 4.2 Cross-Tenant Isolation Breach (Critical Security Incident)
1. **Contain**: If an active IDOR or data leakage vector is reported, immediately disable affected endpoint or isolate affected workspace:
   ```bash
   # Temporarily suspend affected workspace
   psql -U raguard -d raguard_db -c "UPDATE workspaces SET status = 'SUSPENDED' WHERE id = '<tenant-uuid>';"
   ```
2. **Preserve Evidence**: Export active session tokens and database audit logs for the incident timeframe.
3. **Notify**: Escalate immediately to Security Lead and CISO.

### 4.3 PII / Sensitive Data Leakage
1. Identify leaking entity via structured JSON log trace correlation.
2. Update regex rules in `backend/observability/logging/pii_masker.py`.
3. Check `audit_logs` table for queries executed during the vulnerability window.

### 4.4 Audit Log Immutability Violation Suspected
1. Execute table integrity check:
   ```sql
   -- Verify raguard_app role has NO update or delete grants
   SELECT grantee, privilege_type FROM information_schema.role_table_grants WHERE table_name = 'audit_logs';
   ```
2. Verify table schema has no `is_deleted` column.
