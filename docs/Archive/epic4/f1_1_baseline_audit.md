# RAGuard AI — Version 1 Baseline Audit
## Feature F1.1 — Repository & Project Foundation
**Audit Type:** Read-Only | **Date:** 2026-07-30 | **Auditor:** Principal Engineering Manager / ARB

> **Audit Scope:** Review Version 1 production codebase against the approved Version 2 requirements for F1.1. Classify every component and produce a gap analysis. No code was modified during this audit.
> 
> **Dual-Source Validation:** This audit was conducted by direct file inspection of all key source files AND cross-validated by a comprehensive deep-sweep research subagent that traversed the entire repository tree. Both sources are in agreement on all findings below.

---

## Audit Findings Summary

| Category | V1 Status | V2 Requirement | Classification |
| :--- | :--- | :--- | :--- |
| Repository Structure | Mature monorepo | Structured monorepo | ⬆️ Improve |
| Backend Architecture | FastAPI + factory pattern | FastAPI factory pattern | ✅ Reuse As-Is |
| Frontend Architecture | React + Vite + TypeScript | SPA + Vite | ⚠️ Improve |
| Docker Compose (dev) | Two-file include system | Dev compose with all services | ✅ Reuse As-Is |
| Docker Compose (prod) | Exists with all services | Multi-stage production compose | ✅ Reuse As-Is |
| Dockerfile (backend) | Multi-stage (builder/runtime) | Multi-stage, non-root user | ✅ Reuse As-Is |
| Dockerfile (frontend) | Nginx production serve | Nginx production serve | ✅ Reuse As-Is |
| Environment Config | `.env.example` present | `.env.example` + schema validation | ⬆️ Improve |
| Config Management | Modular `pydantic-settings` | Domain-segregated settings | ✅ Reuse As-Is |
| Structured Logging | `structlog` JSON + console | `structlog` JSON with PII masking | ⬆️ Improve |
| Health Endpoints | `/health`, `/health/live`, `/health/ready`, `/health/detailed` | `/health/live`, `/health/ready`, `/health/startup` | ⬆️ Improve |
| Developer Tooling | `Makefile` + `make setup/start/test` | Makefile + script-based onboarding | ✅ Reuse As-Is |
| Linting | `ruff` (comprehensive ruleset) | `ruff` | ✅ Reuse As-Is |
| Type Checking | `mypy` (strict mode) | `mypy` (strict) | ✅ Reuse As-Is |
| Formatting | `ruff format` | `ruff format` | ✅ Reuse As-Is |
| Pre-commit Hooks | **ABSENT** | pre-commit hooks required | 🆕 Implement New |
| CI/CD Pipeline | GitHub Actions (ci.yml, docker-build.yml, release.yml) | GitHub Actions with SAST gate | ⬆️ Improve |
| Testing Foundation | Pytest + Vitest + Playwright structured | Full pyramid with coverage gate | ⬆️ Improve |
| Build Scripts | Scripts in `infrastructure/scripts/` | Bootstrap, reset, health scripts | ✅ Reuse As-Is |
| Local Dev Workflow | `make setup` → docker compose | `make setup` → docker compose | ✅ Reuse As-Is |
| Worker Architecture | **Celery** (not Redis-native queue) | **Redis-native workers** (frozen arch) | 🔴 Replace |
| Supabase Dependency | `@supabase/supabase-js` in frontend | No Supabase (JWT self-hosted auth) | 🔴 Replace |
| Coverage Gate | 70% (pyproject.toml) | ≥85% (Program 2 DoD) | ⬆️ Improve |
| Alembic Root Directory | `alembic/` at root is **EMPTY** | Migrations live at `backend/database/migrations/` | ⬆️ Improve |
| Alembic Migrations | `backend/database/migrations/versions/` is **EMPTY** | Initial schema migrations required | 🆕 Implement New (F1.2) |
| Placeholder Directories | `configs/`, `shared/`, `monitoring/` are all **EMPTY** | Populate or remove | ⬆️ Improve |
| Kubernetes Manifests | All K8s sub-directories are **EMPTY** | Manifests required | 🆕 Implement New (F1.8) |
| `backend/api/v2/` | Scaffold exists (controllers/, routes/, schemas/, dependencies/) but **no files** | V2 routes to be implemented in Epics 2–15 | ✅ Reuse As-Is (scaffold ready) |
| `infrastructure/compose/` | `docker-compose.base.yml`, `.dev.yml`, `.prod.yml` all exist | Reuse as base | ✅ Reuse As-Is |

---

## Detailed Gap Analysis

### 1. Repository Structure
| Dimension | Current State (V1) | Required State (V2) | Recommendation | Reason |
| :--- | :--- | :--- | :--- | :--- |
| Root layout | Backend, frontend, infra, tests, alembic co-located | Same monorepo layout | **Reuse As-Is** | Structure is mature and logically organized. |
| `backend/api/v2/` | Directory exists but is empty | V2 API routes live here | **Reuse (scaffold exists)** | The V2 API directory exists with `routes/`, `schemas/`, `controllers/`, `dependencies/` sub-dirs already created. Ready to receive implementation. |
| `implementation_plan.md` in backend/ | Stray planning file in source directory | Should be in repo root or docs/ | **Improve** | Planning artifacts must not reside inside the `backend/` source package. |

### 2. Backend Architecture
| Dimension | Current State (V1) | Required State (V2) | Recommendation | Reason |
| :--- | :--- | :--- | :--- | :--- |
| Application factory | `create_app()` in `main.py` | Factory pattern required | **Reuse As-Is** | Production-grade factory with lifespan, middleware stack, and exception handlers. |
| Middleware stack | CORS → CorrelationID → Observability → SecurityHeaders → RequestLogging | Same stack required | **Reuse As-Is** | Middleware order is architecturally correct and matches V2 requirements. |
| Config system | Modular Pydantic-settings domains (`AppSettings`, `DatabaseSettings`, etc.) | Domain-segregated settings | **Reuse As-Is** | Excellent design. `get_settings()` LRU-cached singleton. |
| `SupabaseSettings` in config | Supabase config present | No Supabase in V2 | **Remove** | V2 uses self-hosted JWT auth. Supabase is not in the approved technology stack. |
| Startup validator | `startup_validator.py` present | Contract validation at startup | **Reuse As-Is** | Validates critical startup contracts cleanly. |

### 3. Worker Architecture (CRITICAL GAP)
| Dimension | Current State (V1) | Required State (V2) | Recommendation | Reason |
| :--- | :--- | :--- | :--- | :--- |
| Worker technology | **Celery** with Redis broker | **Redis-native worker queue** (ARQ or equivalent) | **Replace** | Program 1 architecture mandates a Redis-native worker architecture. Celery is not in the approved technology stack. This is the most significant gap. The Celery queue definitions and task naming conventions are compatible with the new design; only the broker technology changes. |

### 4. Frontend Architecture
| Dimension | Current State (V1) | Required State (V2) | Recommendation | Reason |
| :--- | :--- | :--- | :--- | :--- |
| Framework | React 18 + Vite + TypeScript | React SPA | **Reuse As-Is** | Framework is fully compliant. |
| Auth client | `@supabase/supabase-js` used for authentication | Self-hosted JWT API calls | **Replace** | Supabase JS client must be removed. All auth calls must route through the V2 Platform API. |
| Design system | `tailwindcss` + Radix UI | CSS Variables design token system | **Improve** | Tailwind utility classes must be supplemented/migrated to a CSS Custom Property (CSS Variable) token system per the Stage 12 architecture decision. The Radix UI primitive components are compliant and can be kept. |
| State management | `zustand` (both `store/` and `stores/` directories exist — duplication) | Single centralized tenant state | **Improve** | The duplicate `store/` and `stores/` directories must be consolidated into a single `stores/` module with a strict workspace context boundary. |
| Linting | ESLint (`.eslintrc.cjs`) | ESLint | **Reuse As-Is** | Configuration is appropriate. |

### 5. Docker & Containers
| Dimension | Current State (V1) | Required State (V2) | Recommendation | Reason |
| :--- | :--- | :--- | :--- | :--- |
| Backend Dockerfile | Multi-stage (builder/runtime), non-root user, healthcheck | Same | **Reuse As-Is** | Fully compliant. Non-root `raguard` user is present. Healthcheck points to `/health`. |
| Python version | Python 3.13 in Dockerfile, 3.12 in pyproject.toml | Consistent Python version | **Improve** | Minor inconsistency: pyproject.toml states `>=3.12` but Dockerfile uses `python:3.13-slim`. Pin to 3.13 explicitly in both. |
| Frontend Dockerfile | Multi-stage Nginx serve | Multi-stage Nginx serve | **Reuse As-Is** | Compliant. |
| `docker-compose.yml` | Includes api, worker, frontend, postgres, redis, qdrant | Same services | **Reuse As-Is** | All required services present with health checks. |
| PgBouncer | **ABSENT** from docker-compose | PgBouncer required in dev | **Implement New** | The approved architecture mandates PgBouncer as the connection pool. It is defined in the architecture (Stage 6) but absent from all Compose files. |

### 6. Environment Configuration
| Dimension | Current State (V1) | Required State (V2) | Recommendation | Reason |
| :--- | :--- | :--- | :--- | :--- |
| `.env.example` | Present with 40 lines covering all core services | Must be updated for V2 | **Improve** | V2 requires new variables: `WORKSPACE_ID` scoping, JWT signing configuration (`JWT_ALGORITHM`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`), and removal of Supabase-specific variables. |
| `.env.local` | Present (1554 bytes) | Local dev overrides | **Reuse As-Is** | Pattern is correct. |
| `.env.prod.example` | Present | Production template | **Improve** | Update to remove Supabase variables and add V2-specific production variables. |

### 7. Logging
| Dimension | Current State (V1) | Required State (V2) | Recommendation | Reason |
| :--- | :--- | :--- | :--- | :--- |
| Library | `structlog` (JSON + console renderer) | `structlog` JSON with PII masking | **Improve** | The logging configuration is excellent. However, V2 requires an explicit PII masking processor in the structlog pipeline. User email addresses, query text, and document content must be redacted before log output. A `_mask_pii` processor step must be added to `configure_logging()`. |
| Log correlation | `CorrelationIDMiddleware` present | Trace ID propagation | **Reuse As-Is** | Correlation ID middleware is production-grade. |

### 8. Health Endpoints
| Dimension | Current State (V1) | Required State (V2) | Recommendation | Reason |
| :--- | :--- | :--- | :--- | :--- |
| `/health` | Present | Present | **Reuse As-Is** | — |
| `/health/live` | Present | Present | **Reuse As-Is** | — |
| `/health/ready` | Present (checks PG, Redis, Qdrant) | Present | **Reuse As-Is** | — |
| `/health/startup` | **ABSENT** | Required (K8s startup probe) | **Implement New** | The startup probe is specifically required for Kubernetes slow-starting pods (e.g., Qdrant, V1 Engine). It differs from the readiness probe in that it blocks traffic only during initial startup. |
| `/health/detailed` | Present (ADMIN-gated) | Present | **Reuse As-Is** | — |

### 9. CI/CD Pipeline
| Dimension | Current State (V1) | Required State (V2) | Recommendation | Reason |
| :--- | :--- | :--- | :--- | :--- |
| `ci.yml` | lint (ruff) + pytest + docker build | lint + SAST + mypy + pytest + coverage gate + docker build + push | **Improve** | Lint step runs with `|| true` (failures are silent). This must be a hard gate. SAST (Bandit/Semgrep), `mypy` type checking, and a coverage enforcement step must be added. |
| `docker-build.yml` | Docker build validation | Build + registry push | **Improve** | Add container registry push step for Staging auto-deploy trigger. |
| `release.yml` | Release workflow | Production release | **Reuse As-Is** | Extend as needed. |
| SAST | **ABSENT** | Bandit / Semgrep required | **Implement New** | No static application security testing step exists. |
| `dependabot.yml` | Present | Present | **Reuse As-Is** | Dependency update automation is in place. |

### 10. Pre-commit Hooks
| Dimension | Current State (V1) | Required State (V2) | Recommendation | Reason |
| :--- | :--- | :--- | :--- | :--- |
| `.pre-commit-config.yaml` | **ABSENT** | Required | **Implement New** | No pre-commit hooks are defined. Engineers can commit unformatted, untyped, or insecure code without any local gate. This is a significant quality gap that must be closed before Feature F1.1 is complete. |

### 11. Testing Foundation
| Dimension | Current State (V1) | Required State (V2) | Recommendation | Reason |
| :--- | :--- | :--- | :--- | :--- |
| Pytest setup | `pyproject.toml` configured, `tests/` pyramid structured (unit, integration, e2e, security, performance, chaos) | Same | **Reuse As-Is** | Excellent structure. Pytest markers already defined. |
| Coverage gate | 70% (`fail_under = 70`) | ≥85% | **Improve** | Must raise the `fail_under` threshold from 70 to 85. |
| `conftest.py` | Present (2903 bytes) | Test fixtures and factories | **Reuse As-Is** | Review during implementation but likely compliant. |
| Frontend tests | Vitest + Playwright configured | Vitest + Playwright | **Reuse As-Is** | Full testing stack is present. |

---

### Additional Findings (Confirmed by Deep-Sweep Research Subagent)

| Finding | Location | Impact | Action Required |
| :--- | :--- | :--- | :--- |
| Root `alembic/` directory is empty | `d:\RAGuard\alembic\` | Confusing — engineers may look here for migrations | Move or symlink to `backend/database/migrations/`; add comment to `alembic.ini` clarifying actual path |
| `versions/` inside migrations is empty | `backend/database/migrations/versions/` | No database schema exists yet | First Alembic revision must be generated in F1.2 |
| `configs/`, `shared/`, `monitoring/` are empty | Root level | Dead directories increase cognitive noise | Populate with appropriate config files in F1.2–F1.6 or remove if unused |
| All Kubernetes manifests are empty | `infrastructure/kubernetes/` | K8s not scaffolded | Scoped to F1.8 Cloud Infrastructure |
| `backend/api/v2/` scaffold exists | `backend/api/v2/controllers/`, `routes/`, `schemas/`, `dependencies/` | V2 endpoint directories already created | No action needed — scaffold is ready to receive implementation starting from Epic 2 |
| `infrastructure/compose/` has all three compose files | `docker-compose.base.yml`, `.dev.yml`, `.prod.yml` | Dev compose include chain is valid | Reuse as-is; add PgBouncer service to `docker-compose.base.yml` |
| `infrastructure/docker/` has Dockerfiles not referenced by main compose | `Dockerfile.backend`, `Dockerfile.backend.prod`, `Dockerfile.frontend`, `Dockerfile.frontend.prod` | Duplicate Dockerfile definitions | Consolidate: root `Dockerfile` is the active one; `infrastructure/docker/` versions to be archived or reconciled |
| `backend/implementation_plan.md` inside source tree | `backend/implementation_plan.md` | Planning artifact in source package | Move to `docs/implementation/` |

---

## Classification Summary

| Classification | Count | Items |
| :--- | :--- | :--- |
| ✅ **Reuse As-Is** | 18 | Backend factory, config system, Makefile, Docker Compose, Dockerfile, ruff, mypy, structlog, health endpoints (3/4), CI structure, testing pyramid, build scripts, dev workflow, middleware stack, frontend framework, ESLint, Playwright |
| ⬆️ **Improve** | 8 | Logging (add PII masking), env config (remove Supabase vars, add JWT vars), CI (add SAST/mypy/coverage gate, hard fail lint), coverage gate (70%→85%), Python version pinning, frontend state consolidation, CSS token system, `implementation_plan.md` location |
| 🔴 **Replace** | 2 | Worker architecture (Celery → Redis-native/ARQ), Frontend Supabase auth client |
| 🆕 **Implement New** | 3 | Pre-commit hooks, `/health/startup` endpoint, PgBouncer in Docker Compose |

---

## F1.1 Implementation Plan (Gaps Only)

The following work is required for F1.1. It focuses **exclusively** on missing or inadequate components, maximising reuse of the V1 baseline.

### Task 1 — Pre-commit Hooks (IMPLEMENT NEW)
**File:** `.pre-commit-config.yaml`
- Add hooks: `ruff-pre-commit` (lint + format), `mypy`, `detect-secrets`, `check-yaml`, `end-of-file-fixer`, `trailing-whitespace`.
- This closes the most critical quality gap.

### Task 2 — PgBouncer in Docker Compose (IMPLEMENT NEW)
**Files:** `infrastructure/compose/docker-compose.base.yml`, `docker-compose.yml`
- Add PgBouncer service (image: `pgbouncer/pgbouncer`) sitting between the application and PostgreSQL.
- Update `DATABASE_URL` in app environment to point to PgBouncer (`localhost:5432` → `pgbouncer:5432`).
- Add PgBouncer config file: `infrastructure/configs/pgbouncer.ini`.

### Task 3 — `/health/startup` Endpoint (IMPLEMENT NEW)
**File:** `backend/api/v1/routes/health.py`
- Add `GET /health/startup` endpoint that mirrors readiness logic but returns `503` during initial boot window and `200` once all clients are initialized.

### Task 4 — PII Masking in Logging (IMPROVE)
**File:** `backend/core/logging/config.py`
- Add a `_mask_pii` processor to the structlog shared pipeline.
- Fields `email`, `query`, `content`, `document_text` must be redacted before serialization.

### Task 5 — CI Pipeline Hardening (IMPROVE)
**File:** `.github/workflows/ci.yml`
- Change `ruff check backend/ || true` to `ruff check backend/` (hard fail).
- Add `mypy backend/ --ignore-missing-imports` step.
- Add `bandit -r backend/ -ll` SAST step.
- Add coverage enforcement: `pytest --cov=backend --cov-fail-under=85`.

### Task 6 — Coverage Gate Increase (IMPROVE)
**File:** `pyproject.toml`
- Change `fail_under = 70` to `fail_under = 85`.

### Task 7 — Remove Supabase Configuration (REPLACE)
**Files:** `backend/core/config/supabase.py`, `backend/core/config/__init__.py`, `.env.example`
- Remove `SupabaseSettings` and its import from `Settings.__init__`.
- Remove `SUPABASE_URL` and `SUPABASE_ANON_KEY` from `.env.example`.
- Add V2-required variables to `.env.example`: `JWT_ALGORITHM`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`, `JWT_REFRESH_TOKEN_EXPIRE_DAYS`.

### Task 8 — Worker Architecture Note (REPLACE — Scoped to F1.3)
- The Celery → ARQ migration is a significant change touching every worker file. It is acknowledged here but scoped to **F1.3 Redis Foundation** rather than F1.1 to maintain vertical slice integrity.

### Task 9 — Move Planning Artifact (IMPROVE)
**File:** `backend/implementation_plan.md`
- Move to `docs/implementation/` or the artifacts directory. Source code directories must not contain planning documents.

### Task 10 — Python Version Pin Consistency (IMPROVE)
**Files:** `Dockerfile`, `pyproject.toml`
- Pin `requires-python = ">=3.13"` in `pyproject.toml` to match the `python:3.13-slim` image used in the Dockerfile.

---

## Definition of Done — F1.1 (Post-Audit Revised)

| Criterion | Target |
| :--- | :--- |
| Pre-commit hooks installed and enforcing | ✅ |
| PgBouncer added to Docker Compose dev stack | ✅ |
| `/health/startup` endpoint live | ✅ |
| PII masking active in structlog pipeline | ✅ |
| CI pipeline: lint is a hard gate | ✅ |
| CI pipeline: mypy + SAST steps added | ✅ |
| Coverage gate raised to 85% | ✅ |
| Supabase settings removed from backend config | ✅ |
| `.env.example` updated with V2 JWT variables | ✅ |
| Python version consistent across Dockerfile and pyproject.toml | ✅ |
| Planning artifact removed from `backend/` source tree | ✅ |
| All existing V1 functionality verified intact | ✅ |

---

## Audit Conclusion

The Version 1 codebase is a **highly mature, production-grade baseline**. The architecture quality is exceptional — the factory pattern, modular config, structlog pipeline, middleware stack, health endpoints, and testing pyramid are all directly reusable. The gaps identified are targeted and tractable.

The **two critical gaps** that must not proceed to implementation are:
1. **Celery worker architecture** — does not comply with the frozen V2 "Redis-native worker" mandate. Scoped to F1.3.
2. **Supabase dependency** — must be removed before any V2 authentication work begins.

With the 10 targeted tasks above completed, F1.1 will be fully compliant with the frozen Program 1 architecture while preserving the entire V1 production baseline.

**Recommendation: PROCEED WITH IMPLEMENTATION (Tasks 1–10 above only).**
