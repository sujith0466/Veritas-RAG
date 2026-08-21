# Rollback & Deployment Recovery Runbook

**Target Audience:** SRE On-Call, Release Engineers, DevOps
**System:** RAGuard V2 Multi-Tenant AI Platform
**Classification:** Core Operational Procedure
**Status:** PRODUCTION READY

---

## 1. Trigger Criteria for Rollback

A rollback must be initiated immediately if any of the following conditions occur post-deployment:
- **Critical Error Spike**: 5xx HTTP error rate exceeds 1% for > 3 minutes (`CriticalAPIErrorRate` alert).
- **Service Unavailability**: Readiness probe failure on > 50% of replicas (`ServiceUnavailable` alert).
- **Data Corruption / Schema Conflict**: Incompatible database queries causing fatal unhandled exceptions.
- **Circuit Breaker Tripped**: Immediate upstream failures with no automatic recovery.

---

## 2. Kubernetes Application Rollback

```bash
# 1. Inspect recent rollout history
kubectl rollout history deployment/raguard-api -n raguard-production

# 2. Undo the rollout to the previous revision
kubectl rollout undo deployment/raguard-api -n raguard-production

# 3. Monitor rollback status
kubectl rollout status deployment/raguard-api -n raguard-production

# 4. Verify pod health and ready states
kubectl get pods -n raguard-production -l app.kubernetes.io/name=raguard
```

---

## 3. Database Migration Rollback (Alembic)

> **Pre-requisite:** Before rolling back database schema, scale down active application pods to prevent schema mismatch exceptions.

```bash
# 1. Scale down backend API pods
kubectl scale deployment/raguard-api -n raguard-production --replicas=0

# 2. Inspect current database revision
alembic current

# 3. Roll back one revision
alembic downgrade -1
# Or roll back to a specific stable revision:
# alembic downgrade <stable_revision_id>

# 4. Confirm target revision is active
alembic current

# 5. Scale API pods back up
kubectl scale deployment/raguard-api -n raguard-production --replicas=3
```

---

## 4. Docker Compose Rollback (Staging / Development)

```bash
# 1. Stop the failing container stack
docker-compose down

# 2. Check out previous release tag or rollback commit
git checkout <previous_stable_tag>

# 3. Rebuild or pull stable images and restart
docker-compose up -d --build

# 4. Verify health endpoints
curl -s http://localhost:8000/health/ready | jq .
```

---

## 5. Post-Rollback Validation Checklist

- [ ] Probe `/health/live` returns HTTP 200 OK.
- [ ] Probe `/health/ready` returns HTTP 200 OK with all dependencies (`postgresql`, `redis`, `qdrant`, `storage`) marked healthy.
- [ ] Prometheus error rate metric `raguard_http_requests_total{status=~"5.."}` drops to 0.
- [ ] Alembic schema version aligns with the running application code.
- [ ] On-call lead updates incident channel with rollback confirmation.
