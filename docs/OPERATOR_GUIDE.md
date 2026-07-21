# Operator Guide

## Daily Operations

### Health Monitoring

```bash
# Check all service health
curl http://localhost:8000/health

# Check Prometheus metrics
curl http://localhost:8000/observability/v1/metrics
```

### Log Monitoring

Logs are emitted as structured JSON. Use your preferred aggregator:

```bash
# Docker
docker-compose logs -f api | jq .

# Filter for errors
docker-compose logs api | jq 'select(.level == "ERROR")'
```

## Incident Response

### Circuit Breaker Open

```bash
# Check circuit state
curl http://localhost:8000/api/v1/reliability/circuit-breaker

# Force reset
curl -X POST http://localhost:8000/api/v1/reliability/circuit-breaker/reset
```

### High Memory / Latency

1. Check Prometheus for `raguard_http_request_duration_seconds_avg`
2. If Qdrant is slow, run Index Advisor:
   ```http
   GET /api/v1/intelligence/v1/insights/<tenant_id>
   ```
3. Apply recommended re-indexing.

## Scaling

```bash
# Scale API instances
docker-compose up -d --scale api=5

# PostgreSQL connection pool (via .env)
DB_POOL_SIZE=50
DB_MAX_OVERFLOW=20
```

## Backup

```bash
# Postgres
pg_dump -U raguard raguard_db > backup.sql

# Qdrant (via API)
curl -X POST http://localhost:6333/snapshots
```
