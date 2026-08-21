# Service Restart & Maintenance Runbook

**Target Audience:** SRE On-Call, DevOps Engineers
**System:** RAGuard V2 Multi-Tenant AI Platform
**Classification:** Core Operational Procedure
**Status:** PRODUCTION READY

---

## 1. Rolling Restart (Zero-Downtime)

To restart the application without interrupting client traffic or dropping active chat sessions:

### Kubernetes Rolling Restart
```bash
# 1. Trigger rolling restart of API deployment
kubectl rollout restart deployment/raguard-api -n raguard-production

# 2. Watch rollout status to ensure new pods pass readiness probes before old pods terminate
kubectl rollout status deployment/raguard-api -n raguard-production
```

### Docker Compose Non-Disruptive Restart
```bash
# Restart background workers without affecting API
docker-compose restart celery-worker

# Restart reverse proxy
docker-compose restart nginx
```

---

## 2. Individual Subsystem Restart Procedures

### 2.1 Redis Restart
```bash
# In Kubernetes:
kubectl rollout restart statefulset/raguard-redis -n raguard-production

# Verification:
redis-cli -h localhost -p 6379 ping
# Expected output: PONG
```

### 2.2 Qdrant Vector Store Restart
```bash
# In Kubernetes:
kubectl rollout restart statefulset/raguard-qdrant -n raguard-production

# Verification:
curl -s http://localhost:6333/healthz
# Expected output: HTTP 200 OK
```

### 2.3 Celery Worker Restart
```bash
# Warm restart sending HUP to Celery workers:
docker-compose kill -s HUP celery-worker
```
