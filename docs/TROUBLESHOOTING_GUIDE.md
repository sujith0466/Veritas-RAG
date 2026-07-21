# Troubleshooting Guide

## Application Won't Start

**Symptom**: `uvicorn` exits immediately.

**Checks**:
1. Verify `.env` has all required variables: `SECRET_KEY`, `DATABASE_URL`.
2. Ensure PostgreSQL is running: `docker-compose ps`.
3. Run migrations: `alembic upgrade head`.

## Low Confidence Scores

**Symptom**: Answers return `reliability_status: LOW`.

**Checks**:
1. Check retrieval quality: `GET /api/v1/retrieval/metrics`.
2. Verify document embeddings are current: check knowledge health.
3. Review similarity threshold in configuration.
4. Run Index Advisor: `GET /api/v1/intelligence/v1/insights/{tenant_id}`.

## Circuit Breaker Open

**Symptom**: `503` errors on generation endpoints.

**Resolution**:
1. Check circuit state: `GET /api/v1/reliability/circuit-breaker`.
2. Verify LLM provider API key is valid.
3. Wait for automatic recovery window or force reset:
   `POST /api/v1/reliability/circuit-breaker/reset`.

## High Latency

**Symptom**: Requests taking >2 seconds.

**Checks**:
1. Check `raguard_http_request_duration_seconds_avg` in Prometheus.
2. Inspect Qdrant query latency.
3. Check Redis connection: `redis-cli ping`.
4. Review DB connection pool: look for `QueuePool limit exceeded` in logs.

## Quota Exceeded

**Symptom**: `429 Too Many Requests` with code `RATE_001`.

**Resolution**: Update quota via Admin API or wait for monthly reset.
