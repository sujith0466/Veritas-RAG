# Backup & Restoration Runbook

**Target Audience:** SRE On-Call, Database Administrators, DevOps
**System:** RAGuard V2 Multi-Tenant AI Platform
**Classification:** Core Operational Procedure
**Status:** PRODUCTION READY

---

## 1. Overview & Architecture

RAGuard implements automated scheduled backups across all persistent state engines using Kubernetes CronJobs and volume-backed persistence.

### Backup Schedule Matrix

| Datastore | Mechanism | Schedule | Target Location / PVC | Retention |
|:---|:---|:---|:---|:---|
| **PostgreSQL** | `pg_dump` via `postgres-backup` CronJob | `0 2 * * *` (Daily 02:00 UTC) | `postgres-backup-pvc` (`/backup/db_YYYYMMDD.sql`) | 30 Days |
| **MinIO (S3)** | `mc mirror` via `minio-backup` CronJob | `0 3 * * *` (Daily 03:00 UTC) | S3 Backup Bucket / Local Mirror | 30 Days |
| **Qdrant** | REST Snapshot API (`/snapshots`) | `0 4 * * *` (Daily 04:00 UTC) | `/qdrant/storage/snapshots/` | 14 Days |
| **Redis** | Ephemeral | None | In-memory with optional AOF | Ephemeral |

---

## 2. Backup Integrity Verification

Before initiating any recovery, the on-call engineer must verify the backup file's integrity:

### 2.1 PostgreSQL Dump Verification
```bash
# 1. Check file existence and non-zero size
ls -lh /backup/db_*.sql

# 2. Verify SQL header / dump format
head -n 20 /backup/db_$(date +%Y%m%d).sql | grep "PostgreSQL database dump"
```

### 2.2 Qdrant Snapshot Verification
```bash
# 1. Query available snapshots via REST API
curl -s http://raguard-qdrant:6333/collections/knowledge/snapshots | jq .

# 2. Verify snapshot checksum and creation timestamp
```

---

## 3. Step-by-Step Restoration Procedures

### 3.1 PostgreSQL Restoration

> **Safety Warning:** Restoring PostgreSQL drops and recreates schema tables. In a production environment, you must pass `--confirm`.

```bash
# 1. Scale down backend API pods to prevent active database transactions
kubectl scale deployment/raguard-api -n raguard-production --replicas=0
# Or in Docker Compose:
docker-compose stop backend

# 2. Execute automated restoration script
bash infrastructure/scripts/dr/restore_postgres.sh /backup/db_20260821.sql --confirm

# 3. Verify Alembic schema migration status
alembic current

# 4. Scale backend API pods back to target replica count
kubectl scale deployment/raguard-api -n raguard-production --replicas=3
# Or in Docker Compose:
docker-compose start backend
```

### 3.2 Qdrant Vector Collection Restoration

```bash
# 1. Execute Qdrant snapshot recovery script
bash infrastructure/scripts/dr/restore_qdrant.sh knowledge "file:///qdrant/storage/snapshots/knowledge-snapshot.snapshot" --confirm

# 2. Verify collection health status
curl -s http://localhost:6333/collections/knowledge | jq .result.status
# Expected output: "green" or "ok"
```

### 3.3 MinIO Object Storage Restoration

```bash
# 1. Obtain root credentials from Kubernetes secret
MINIO_PASSWORD=$(kubectl get secret raguard-secrets -n raguard-production -o jsonpath="{.data.MINIO_ROOT_PASSWORD}" | base64 -d)

# 2. Synchronize backup bucket back to active storage
mc alias set local http://raguard-minio:9000 admin "$MINIO_PASSWORD"
mc mirror s3/backup local/data
```

---

## 4. Post-Restore Health Validation

Always run the automated verification script after restoring services:

```bash
bash infrastructure/scripts/dr/verify_restore.sh http://localhost:8000
```

Expected output:
```
[*] Step 1/3: Validating application liveness (/health/live)...
[+] Liveness check passed (HTTP 200).
[*] Step 2/3: Validating subsystem readiness (/health/ready)...
[+] Readiness check passed (HTTP 200). Subsystems are operational.
============================================================
[+] POST-RESTORE VERIFICATION SUCCESSFUL
============================================================
```

---

## 5. Escalation & Ownership Matrix

| Subsystem | Primary Owner | Escalation Contact | SLA |
|:---|:---|:---|:---|
| PostgreSQL DB | Database Lead | SRE On-Call (PagerDuty) | 15 Minutes |
| Qdrant Vector DB | AI Platform Lead | SRE On-Call (PagerDuty) | 15 Minutes |
| MinIO Storage | Infrastructure Lead | SRE On-Call (PagerDuty) | 30 Minutes |
| API / FastApi | Backend Lead | SRE On-Call (PagerDuty) | 15 Minutes |
