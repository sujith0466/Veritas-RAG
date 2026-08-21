# Veritas RAG — Infrastructure Guide

**Document Version**: 1.0.0
**Phase**: Phase 1 — Foundation & Enterprise Setup
**Milestone**: Milestone 5 — Infrastructure & Developer Environment
**Status**: Approved & Frozen Baseline

---

## 1. Overview & Core Rules

Veritas RAG enforces a strict **Zero-Leakage Environment Strategy**. Configuration separation between local development, staging, and production is managed via Pydantic `BaseSettings` (`backend/core/config/`) on the backend and `import.meta.env` (`vite.config.ts`) on the frontend.

### 1.1 Non-Negotiable Rules
1. **Never Commit Secrets**: No actual password, API key, JWT secret, or private database connection string may ever be committed to git. `.gitignore` strictly ignores `.env`, `.env.local`, `.env.test`, `.env.development`, and `.env.production`.
2. **Commit Only Templates**: Only `.env.example` (at repository root) and `infrastructure/env/*.template` files are tracked by git. These templates must contain placeholder documentation (`your-openrouter-key-here`) and safe local defaults (`postgres:password@localhost:5432/raguard`).
3. **Mandatory Pre-Flight Validation**: Before starting services or executing database migrations, `infrastructure/env/validate_env.py` runs automatically to verify schema validity, port integers, and driver strings (`postgresql+asyncpg://`).

---

## 2. Environment File Override Hierarchy

When `docker compose up -d` or Uvicorn starts, configuration values are resolved using the following priority order (from highest to lowest priority):

```
+-------------------------------------------------------------------------+
| Priority 1: Operating System & CI/CD Process Environment Variables       |
|             (e.g., exported via terminal or injected by GitHub Actions) |
+-------------------------------------------------------------------------+
                                     │
                                     ▼
+-------------------------------------------------------------------------+
| Priority 2: Docker Compose Environment Section / Docker Secrets        |
|             (Values explicitly passed in docker-compose.dev/prod.yml)   |
+-------------------------------------------------------------------------+
                                     │
                                     ▼
+-------------------------------------------------------------------------+
| Priority 3: Local Developer Override File (`.env.local`)                |
|             (Created from `.env.example` during make setup / bootstrap) |
+-------------------------------------------------------------------------+
                                     │
                                     ▼
+-------------------------------------------------------------------------+
| Priority 4: Pydantic Field Defaults (`backend/core/config/*.py`)        |
|             (Hardcoded fallback values for non-sensitive local parameters)|
+-------------------------------------------------------------------------+
```

---

## 3. Comprehensive Variable Reference (`.env.example` Inventory)

### 3.1 Application Identity & Server (`APP_*`, `SERVER_*`)
| Variable Name | Default / Template Value | Purpose & Validation Rules |
| :--- | :--- | :--- |
| `APP_NAME` | `Veritas RAG` | Display name of the platform across logs and API docs. |
| `APP_VERSION` | `1.0.0` | SemVer string reported by `GET /api/v1/health`. |
| `APP_ENVIRONMENT` | `development` | Runtime mode: `development`, `testing`, `staging`, or `production`. |
| `APP_DEBUG` | `True` (dev) / `False` (prod) | Enables tracebacks in responses (Must be `False` in prod). |
| `APP_SECRET_KEY` | `dev_secret_key_change_in_production_32bytes` | Cryptographic secret for cookie signatures and CSRF protection. |
| `SERVER_HOST` | `0.0.0.0` | Interface binding for Uvicorn ASGI server. |
| `SERVER_PORT` | `8000` | Port binding for Uvicorn (`validate_env.py` checks 1024-65535). |
| `SERVER_WORKERS` | `1` (dev) / `4` (prod) | Number of Uvicorn multi-process workers when running under Gunicorn. |

### 3.2 Database Engines (`DATABASE_*`, `REDIS_*`, `QDRANT_*`)
| Variable Name | Default / Template Value | Purpose & Validation Rules |
| :--- | :--- | :--- |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:password@postgres:5432/raguard` | Async SQLAlchemy connection string. Must start with `postgresql+asyncpg://`. |
| `ALEMBIC_DATABASE_URL` | `postgresql+asyncpg://postgres:password@postgres:5432/raguard` | Target URL used by Alembic migration scripts (`alembic upgrade head`). |
| `DATABASE_POOL_SIZE` | `10` | Base number of persistent database connections maintained in the pool. |
| `DATABASE_MAX_OVERFLOW`| `20` | Maximum temporary connection burst above pool size. |
| `POSTGRES_DB` | `raguard` | Database name initialized by PostgreSQL container at volume creation. |
| `POSTGRES_USER` | `postgres` | Superuser account initialized by PostgreSQL container. |
| `POSTGRES_PASSWORD` | `password` | Password for `POSTGRES_USER` (`validate_env.py` checks non-empty). |
| `REDIS_HOST` | `redis` | Hostname of Redis service (`veritas-rag-network` internal DNS or IP). |
| `REDIS_PORT` | `6379` | Port binding for Redis server (`6379`). |
| `REDIS_PASSWORD` | `""` (dev) / `secure_redis_pass` (prod)| Password required if Redis `requirepass` is enabled. |
| `CELERY_BROKER_URL` | `redis://redis:6379/1` | Redis database `DB 1` used by Celery task broker. |
| `CELERY_RESULT_BACKEND`| `redis://redis:6379/2` | Redis database `DB 2` used for async task result storage. |
| `QDRANT_HOST` | `qdrant` | Hostname of Qdrant vector store (`veritas-rag-network` internal DNS). |
| `QDRANT_PORT` | `6333` | REST API port for Qdrant operations and health checks. |
| `QDRANT_GRPC_PORT` | `6334` | High-throughput gRPC port for Qdrant vector streaming. |
| `QDRANT_API_KEY` | `""` (dev) / `qdrant_secret_key` (prod) | API key authentication for Qdrant access (`required` in staging/prod). |

### 3.3 Supabase Authentication (`SUPABASE_*`)
| Variable Name | Default / Template Value | Purpose & Validation Rules |
| :--- | :--- | :--- |
| `SUPABASE_URL` | `https://your-supabase-project.supabase.co` | Project URL from Supabase dashboard. |
| `SUPABASE_ANON_KEY` | `your-supabase-anon-key` | Public browser-safe API key exposed to Vite and React. |
| `SUPABASE_SERVICE_ROLE_KEY`| `your-supabase-service-role-key` | Backend-only administrative key with RLS bypass privileges (**NEVER** in `VITE_*`). |
| `SUPABASE_JWT_SECRET` | `your-supabase-jwt-secret` | RS256/HS256 cryptographic secret used by `auth_middleware.py` to verify tokens. |
| `SUPABASE_JWT_ALGORITHM`| `HS256` | JWT signing algorithm (`HS256` for local/dev, `RS256` with JWKS for production). |

### 3.4 AI Providers (`OPENROUTER_*`, `GEMINI_*`, `LLM_*`)
| Variable Name | Default / Template Value | Purpose & Validation Rules |
| :--- | :--- | :--- |
| `OPENROUTER_API_KEY` | `your-openrouter-api-key` | API key for OpenRouter models (`claude-3.5-sonnet`, etc.). |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | Canonical endpoint for OpenRouter completions. |
| `GEMINI_API_KEY` | `your-google-gemini-api-key` | API key for Google Gemini API (`gemini-2.0-flash`). |
| `LLM_PROVIDER_PRIORITY`| `openrouter,gemini` | Comma-separated failover priority chain managed by `LLMManagerSettings`. |

### 3.5 Frontend & Security (`VITE_*`, `CORS_*`)
| Variable Name | Default / Template Value | Purpose & Validation Rules |
| :--- | :--- | :--- |
| `VITE_API_BASE_URL` | `http://localhost:8000` | Base URL used by `apiClient.ts` when running frontend dev server locally. |
| `VITE_SUPABASE_URL` | `https://your-supabase-project.supabase.co` | Supabase URL injected into React bundle. |
| `VITE_SUPABASE_ANON_KEY`| `your-supabase-anon-key` | Public anonymous key injected into React bundle. |
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:3000` | Comma-separated allowed origins checked by FastAPI `CORSMiddleware`. |

---

## 4. Production Secrets Management Pattern

When deploying to Kubernetes or enterprise cloud environments, reading plaintext `.env` files from disk is prohibited. Veritas RAG supports **Docker Secrets** and **Kubernetes Secret Volume Mounts** out of the box:

### 4.1 How Secret Loading Works
For sensitive attributes (`SUPABASE_JWT_SECRET`, `POSTGRES_PASSWORD`, `OPENROUTER_API_KEY`, `GEMINI_API_KEY`), Pydantic settings models verify whether a file path (`/run/secrets/<variable_name>`) exists before reading the environment variable directly:
```python
# In production container runtime:
# If /run/secrets/POSTGRES_PASSWORD exists, its contents override POSTGRES_PASSWORD env var.
```

### 4.2 Rotating Secrets without Downtime
Because `Settings` is loaded into a singleton cached via `@lru_cache(maxsize=1)`, rotating a secret in Kubernetes requires:
1. Updating the Kubernetes Secret object (`kubectl apply -f secret.yaml`).
2. Triggering a rolling deployment (`kubectl rollout restart deployment/backend`), allowing new pods to read the fresh secrets while old pods drain requests cleanly within their 30-second `SIGTERM` window.
