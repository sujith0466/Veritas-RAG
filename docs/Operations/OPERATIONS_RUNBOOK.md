# Master Operations & SRE Runbook Guide

**System**: RAGuard V2 Multi-Tenant Enterprise AI Platform
**Epic**: Epic 15 — Production Hardening & Enterprise Security
**Feature**: F15.8 — Runbook Finalization
**Status**: PRODUCTION READY
**Classification**: Central SRE Operations Reference

---

## 1. Operational Runbook Directory

All operational procedures are codified in dedicated, executable runbooks under [`docs/Runbooks/`](file:///d:/RAGuard/docs/Runbooks/):

| Runbook | Location | Purpose & Trigger |
|:---|:---|:---|
| **Incident Response** | [`incident-response.md`](file:///d:/RAGuard/docs/Runbooks/incident-response.md) | SEV-1/2/3 triage, Prometheus alert resolution, security incidents, PII leakage |
| **Disaster Recovery** | [`disaster-recovery.md`](file:///d:/RAGuard/docs/Runbooks/disaster-recovery.md) | Catastrophic loss of database, vector engine, or cluster |
| **Backup & Restoration** | [`backup-recovery.md`](file:///d:/RAGuard/docs/Runbooks/backup-recovery.md) | Scheduled backup verification, PVC management, `restore_postgres.sh`, `restore_qdrant.sh` |
| **Health Checks & Probes** | [`health-checks.md`](file:///d:/RAGuard/docs/Runbooks/health-checks.md) | Kubernetes liveness (`/live`), readiness (`/ready`), and startup (`/startup`) probes |
| **Rollback & Recovery** | [`rollback-procedure.md`](file:///d:/RAGuard/docs/Runbooks/rollback-procedure.md) | Emergency deployment rollbacks (K8s rollout undo, Alembic schema downgrade) |
| **Service Startup** | [`startup-runbook.md`](file:///d:/RAGuard/docs/Runbooks/startup-runbook.md) | Dependency-ordered cold-start bootstrapping sequence |
| **Graceful Shutdown** | [`shutdown-runbook.md`](file:///d:/RAGuard/docs/Runbooks/shutdown-runbook.md) | Traffic draining, worker warm-shutdown, datastore checkpoints |
| **Service Restart** | [`service-restart.md`](file:///d:/RAGuard/docs/Runbooks/service-restart.md) | Rolling zero-downtime restarts for API pods and stateful backends |
| **Load Testing** | [`load-testing.md`](file:///d:/RAGuard/docs/Runbooks/load-testing.md) | k6 performance testing, quota atomic UPSERT concurrency validation |
| **Chaos Engineering** | [`chaos-engineering.md`](file:///d:/RAGuard/docs/Runbooks/chaos-engineering.md) | Fault policy injection, pod termination drills, blast-radius governance |

---

## 2. Operational Ownership & Escalation Matrix

| Operational Domain | Primary Lead | Secondary On-Call | Escalation Threshold |
|:---|:---|:---|:---|
| **Platform & Gateway** | SRE Team Lead | DevOps Engineer | 5xx error rate > 1% (5 mins) |
| **PostgreSQL Database** | Database Lead | SRE On-Call | Connection pool > 85%, replication lag > 30s |
| **Qdrant Vector DB** | AI Infrastructure Lead | SRE On-Call | Vector drop / snapshot recovery failure |
| **Redis Cache / Broker** | Infrastructure Lead | Backend Engineer | Memory exhaustion > 90% |
| **MinIO Object Store** | Infrastructure Lead | DevOps Engineer | PVC capacity > 80% |
| **Kubernetes Cluster** | Infrastructure Lead | Cloud Platform Team | Node pressure / pod scheduling failure |
| **Security & Compliance** | Security Lead / CISO | SRE Incident Commander | Active cross-tenant breach / key exposure |
| **AI / LLM Gateways** | AI Platform Lead | Backend Engineer | Circuit breaker tripped / provider outage |

---

## 3. Routine Maintenance & Health Checklist

### Daily Checks
- [ ] Verify `postgres-backup` CronJob completed at 02:00 UTC.
- [ ] Verify `minio-backup` CronJob completed at 03:00 UTC.
- [ ] Verify `qdrant-snapshot` CronJob completed at 04:00 UTC.
- [ ] Check Grafana dashboard for unhandled 5xx errors or elevated P95 latency.

### Weekly Checks
- [ ] Run `bash infrastructure/scripts/dr/verify_restore.sh` against staging.
- [ ] Review `audit_logs` table row counts and verify WORM append-only integrity.
- [ ] Validate disk usage on all persistent volumes (`kubectl get pvc`).
