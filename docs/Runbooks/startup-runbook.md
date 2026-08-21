# Service Startup & Initialization Runbook

**Target Audience:** SRE On-Call, Infrastructure Engineers, DevOps
**System:** Veritas RAG — An Enterprise Knowledge Reliability Platform for Self-Correcting Retrieval-Augmented Generation
**Classification:** Core Operational Procedure
**Status:** PRODUCTION READY

---

## 1. Dependency Initialization Order

To prevent connection pool exhaustion and race conditions during cluster startup, services MUST be initialized in the following strictly ordered phases:

```
[Phase 1: Persistent Datastores]
    ├── PostgreSQL (Port 5432)
    ├── Redis (Port 6379)
    ├── Qdrant (Port 6333 / 6334)
    └── MinIO S3 (Port 9000 / 9001)
         │
[Phase 2: Database Schema & Ingestion Queue]
    ├── Alembic Migrations (`alembic upgrade head`)
    └── Celery Background Workers
         │
[Phase 3: Core Application & Gateway]
    ├── FastAPI Backend API (Port 8000)
    └── Nginx Reverse Proxy (Port 80 / 443)
         │
[Phase 4: Telemetry & Observability Stack]
    ├── OpenTelemetry Collector
    ├── Prometheus Scraper
    ├── Grafana Dashboard
    └── Loki Log Aggregator
```

---

## 2. Docker Compose Cold-Start (Staging / Development)

```bash
# 1. Start persistent datastores first
docker-compose up -d postgres redis qdrant minio

# 2. Wait for datastores to become healthy
until docker-compose exec postgres pg_isready -U raguard -d raguard_db; do
    echo "Waiting for PostgreSQL..."
    sleep 2
done

# 3. Execute database migrations
docker-compose run --rm backend alembic upgrade head

# 4. Start remaining application services and workers
docker-compose up -d

# 5. Verify system startup
curl -s http://localhost:8000/health/ready | jq .
```

---

## 3. Kubernetes Cluster Startup

```bash
# 1. Apply core namespaces and secrets
kubectl apply -f infrastructure/kubernetes/namespaces/
kubectl apply -f infrastructure/kubernetes/secrets/
kubectl apply -f infrastructure/kubernetes/configmaps/

# 2. Apply storage classes and PVCs
kubectl apply -f infrastructure/kubernetes/storageclasses/

# 3. Deploy API and services
kubectl apply -f infrastructure/kubernetes/deployments/
kubectl apply -f infrastructure/kubernetes/services/
kubectl apply -f infrastructure/kubernetes/ingress/

# 4. Monitor startup probe completion
kubectl get pods -n raguard-production -w
```

---

## 4. Post-Startup Smoke Test

```bash
# Verify startup probe
curl -f http://localhost:8000/health/startup

# Verify readiness probe
curl -f http://localhost:8000/health/ready
```
