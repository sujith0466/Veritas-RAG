# Deployment Guide

## Docker Compose (Single-Node)

```bash
# Production deployment
ENVIRONMENT=production docker-compose up -d

# Scale API horizontally
docker-compose up -d --scale api=3
```

## Kubernetes (Multi-Node)

1. Build and push Docker image:
   ```bash
   docker build -t your-registry/raguard:1.0.0 .
   docker push your-registry/raguard:1.0.0
   ```

2. Deploy with Helm (chart in `deploy/helm/`):
   ```bash
   helm install raguard ./deploy/helm --set image.tag=1.0.0
   ```

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
