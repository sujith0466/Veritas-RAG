# Database Documentation

## Technology Stack

- **Primary DB**: PostgreSQL 15 (async via asyncpg + SQLAlchemy 2.x)
- **Vector DB**: Qdrant (dense embeddings, multi-tenant collections)
- **Cache**: Redis 7 (atomic quotas, circuit-breaker state, dedup sets)

## PostgreSQL Tables

| Table | Primary Key | Description |
|-------|-------------|-------------|
| `users` | UUID | User accounts and profiles |
| `audit_logs` | UUID | Immutable compliance trail |
| `retrieval_query_logs` | UUID | Search performance records |
| `confidence_scores` | UUID | Per-query confidence history |
| `retry_log` | UUID | Retry budget consumption |
| `alert_rules` | UUID | Alert rule configurations |
| `alert_history` | UUID | Fired alert history |
| `self_healing_policies` | UUID | Healing policy registry |
| `healing_action_log` | UUID | Recovery action audit trail |
| `tenant_quotas` | UUID | Token and cost limits |
| `token_usage` | UUID | Per-request token ledger |
| `fault_policies` | UUID | Chaos injection policies |

## Alembic Migrations

Migrations live in `alembic/versions/`. Each is named `NNNN_<description>.py`.

```bash
# Apply all migrations
alembic upgrade head

# Rollback one version
alembic downgrade -1

# Check current revision
alembic current
```

## Connection Pool Settings

```python
pool_size = 50
max_overflow = 20
pool_timeout = 30
pool_recycle = 1800
```

## Qdrant Collections

Collections are namespaced per tenant: `{tenant_id}_documents`.
Each vector has payload metadata: `doc_id`, `chunk_index`, `source_url`, `ingested_at`.
