# Incident Response Runbook

## 1. Alert Triage Matrix

| Alert Name | Severity | Escalation | First Responder Action |
|---|---|---|---|
| `ServiceUnavailable` | **SEV-1** | PagerDuty (Immediate) | 1. Check pod status: `kubectl get pods -n raguard`<br>2. Inspect container crashes / OOM kills.<br>3. Restart failing backend replicas. |
| `CriticalAPIErrorRate` | **SEV-1** | PagerDuty (Immediate) | 1. Check HTTP 5xx error logs in Grafana.<br>2. Identify failing routes or database timeouts.<br>3. Enable circuit breaker or roll back recent deployment if error spike correlates with release. |
| `QdrantVectorDBUnavailable` | **SEV-1** | PagerDuty (Immediate) | 1. Check Qdrant cluster health (`curl http://qdrant:6333/healthz`).<br>2. Check host memory exhaustion.<br>3. Restart Qdrant service. |
| `CircuitBreakerTripped` | **SEV-1** | PagerDuty (Immediate) | 1. Inspect LLM provider rate limits or outage status.<br>2. Failover to secondary LLM provider or increase retry backoff. |
| `HighAPIRequestLatency` | **SEV-2** | 15m Escalation | 1. Inspect P95 latency breakdown panel in Grafana.<br>2. Check if slow queries are hitting PostgreSQL or dense vector search in Qdrant. |
| `ObjectStorageHighFailureRate` | **SEV-2** | 15m Escalation | 1. Check MinIO / S3 credentials and endpoint reachability.<br>2. Verify storage disk space and bucket permissions. |
| `LowCacheHitRatio` | **SEV-3** | Daily Triage | 1. Inspect Redis TTL configurations and key eviction policies.<br>2. Check if cache invalidations are occurring too aggressively. |

---

## 2. Security Incident Procedures

### 2.1 Compromised LLM / Provider API Key
1. Navigate to Secret Manager / Vault.
2. Rotate API keys for the compromised provider.
3. Update environment secret injection and trigger rolling restart.
4. Verify structured logs for unauthorized usage during the incident window.

### 2.2 PII Leakage / Data Loss Prevention
1. Identify leaking entity via structured JSON log trace correlation.
2. Update regex rules in `backend/observability/logging/pii_masker.py`.
3. Check `audit_logs` table for queries executed during the vulnerability window.
