# Configuration Guide

All configuration is managed via environment variables, loaded through
the Pydantic Settings classes in `backend/configs/`.

## Core Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ENVIRONMENT` | `development` | Runtime environment (`production` activates safety fences) |
| `SECRET_KEY` | — | JWT signing secret (required) |
| `DATABASE_URL` | — | PostgreSQL async URL |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant gRPC/HTTP endpoint |
| `QDRANT_API_KEY` | — | Qdrant API key (optional) |

## LLM Provider Variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key |
| `OPENAI_MODEL` | Default model (e.g. `gpt-4o`) |
| `ANTHROPIC_API_KEY` | Anthropic Claude API key |
| `LLM_PRIORITY_LIST` | Comma-separated provider order |

## Observability Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OTLP_ENDPOINT` | `None` | OpenTelemetry collector endpoint |
| `METRICS_ENABLED` | `True` | Enable Prometheus metrics |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

## Security Variables

| Variable | Description |
|----------|-------------|
| `DLP_ENABLED` | Enable PII redaction before LLM calls |
| `AUDIT_LOG_ENABLED` | Enable compliance audit trail |

See `.env.example` for the complete list with descriptions.
