# Graceful Service Shutdown Runbook

**Target Audience:** SRE On-Call, Infrastructure Engineers, DevOps
**System:** RAGuard V2 Multi-Tenant AI Platform
**Classification:** Core Operational Procedure
**Status:** PRODUCTION READY

---

## 1. Graceful Shutdown Order

To prevent in-flight data loss, dropped SSE streaming connections, or database corruption during maintenance, follow this exact teardown order:

```
[Phase 1: Ingress & Public Traffic]
    └── Nginx Gateway / Kubernetes Ingress (Stop routing new requests)
         │
[Phase 2: Application Draining]
    ├── FastAPI Backend API (Allow 30s grace period for in-flight requests)
    └── Celery Ingestion Workers (Warm shutdown: finish active chunking/embedding jobs)
         │
[Phase 3: Telemetry Flushes]
    ├── OpenTelemetry Collector (Flush pending span queues)
    └── Prometheus / Loki
         │
[Phase 4: Datastores & Caches]
    ├── Redis (Issue SAVE / BGSAVE if persistence required)
    ├── Qdrant (Flush snapshot cache)
    └── PostgreSQL (Issue CHECKPOINT and shutdown)
```

---

## 2. Docker Compose Controlled Shutdown

```bash
# 1. Stop web gateway and frontend
docker-compose stop nginx frontend

# 2. Stop backend and allow worker jobs to complete
docker-compose stop backend celery-worker

# 3. Stop observability services
docker-compose stop prometheus grafana otel-collector loki

# 4. Checkpoint database and stop datastores
docker-compose exec postgres psql -U raguard -d raguard_db -c "CHECKPOINT;"
docker-compose stop postgres redis qdrant minio
```

---

## 3. Kubernetes Pod Eviction & Node Drain

```bash
# 1. Cordon and drain node safely (honoring PodDisruptionBudgets)
kubectl drain <node-name> --ignore-daemonsets --delete-emptydir-data

# 2. Scale deployment down gracefully
kubectl scale deployment/raguard-api -n raguard-production --replicas=0
```
