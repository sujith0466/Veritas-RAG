# Veritas RAG — Deployment Guide

## Docker Compose (Single-Node Multi-Container)

```bash
# Production deployment
docker compose up -d --build

# Apply database migrations
docker compose exec api alembic upgrade head

# Scale API horizontally
docker compose up -d --scale api=3
```

## Kubernetes (Multi-Node Production Architecture)

Modular Kubernetes manifests are provided under `infrastructure/kubernetes/` for deployment to production or staging clusters. *(Note: Helm packaging is planned for a future release; manifests currently use standard Kubernetes YAML resources rather than Kustomize roots or Helm charts).*

### Prerequisites

1. Build and push production container images:
   ```bash
   docker build -t your-registry/veritas-rag:1.0.1 .
   docker push your-registry/veritas-rag:1.0.1
   ```

2. Target namespace creation (`namespaces/namespaces.yaml` configures `veritas-rag-production`, `veritas-rag-staging`, and `raguard-dev`):
   ```bash
   kubectl apply -f infrastructure/kubernetes/namespaces/
   ```

3. Provision required ConfigMaps and Secrets:
   ```bash
   kubectl apply -f infrastructure/kubernetes/configmaps/
   kubectl apply -f infrastructure/kubernetes/secrets/
   ```
   *(Ensure `veritas-rag-config` and `veritas-rag-secrets` are populated with production PostgreSQL, Redis, and Qdrant credentials before proceeding).*

4. Apply workloads, networking, and autoscaling in order:
   ```bash
   kubectl apply -f infrastructure/kubernetes/storageclasses/
   kubectl apply -f infrastructure/kubernetes/deployments/
   kubectl apply -f infrastructure/kubernetes/services/
   kubectl apply -f infrastructure/kubernetes/ingress/
   kubectl apply -f infrastructure/kubernetes/hpa/
   kubectl apply -f infrastructure/kubernetes/networkpolicies/
   ```

> **Deployment Verification Status:** Multi-container Docker Compose is verified live in local and integration testing. Multi-node Kubernetes deployment manifests serve as production infrastructure definitions and must be validated against a live target cluster before production promotion.

## Database Migrations

Always run migrations before starting the API:
```bash
alembic upgrade head
```

## Health Checks

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Overall health (liveness) |
| `GET /health/liveness` | Kubernetes liveness probe |
| `GET /health/readiness` | Kubernetes readiness probe |
| `GET /observability/v1/metrics` | Prometheus metrics |

## Environment-Specific Configurations

| Environment | Key Settings |
|-------------|-------------|
| `development` | Debug mode, reload, mock LLM providers |
| `staging` | Real providers, relaxed rate limits |
| `production` | HSTS, chaos fencing, strict quotas |
