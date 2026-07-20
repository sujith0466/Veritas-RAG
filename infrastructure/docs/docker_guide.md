# RAGuard AI — Docker Guide & Multi-Stage Build Specifications

**Document Version**: 1.0.0  
**Phase**: Phase 1 — Foundation & Enterprise Setup  
**Milestone**: Milestone 5 — Infrastructure & Developer Environment  
**Status**: Approved & Frozen Baseline  

---

## 1. Overview & Objectives

The RAGuard AI platform leverages multi-stage Docker builds to achieve two conflicting enterprise goals without compromise:
1. **Developer Velocity (`dev` target)**: Sub-second hot-reloading (`--reload` / Vite HMR), rich debugging tools, readable tracebacks, and volume-mounted source directories.
2. **Production Security & Efficiency (`prod` target)**: Stripped build artifacts, minimal attack surface (distroless/slim images), non-root execution (`UID 10001`), immutable image layers, and pre-compiled bytecode/bundles.

---

## 2. Backend Multi-Stage Architecture (`Dockerfile.backend`)

`infrastructure/docker/Dockerfile.backend` is structured into four distinct, cache-optimized stages:

```
[stage: base] (python:3.12-slim-bookworm)
      │
      ├── Setup ENV: PYTHONUNBUFFERED=1, PYTHONDONTWRITEBYTECODE=1
      └── Install runtime libs: libpq-dev, curl, ca-certificates
      │
      ▼
[stage: dependencies]
      │
      ├── Create Virtualenv /opt/venv
      ├── Copy requirements/base.txt & requirements/dev.txt
      └── Run pip install --no-cache-dir -r requirements/dev.txt
      │
      ├─────────────────────────────────────────────┐
      ▼                                             ▼
[stage: dev] (Default target)               [stage: prod] (Production target)
      │                                             │
      ├── Inherit /opt/venv                         ├── Copy /opt/venv from [dependencies]
      ├── Create non-root user 'raguard'            ├── Copy application source ./backend -> /app/backend
      ├── Mount ./backend at runtime                ├── Create non-root user (UID 10001) & drop root
      └── CMD uvicorn --host 0.0.0.0 --reload       └── CMD gunicorn -w 4 -k uvicorn.workers.UvicornWorker
```

### 2.1 Caching Strategy
By copying only `requirements/*.txt` into the `dependencies` stage before copying application source code (`backend/`), Docker caches the entire pip virtualenv (`/opt/venv`). Code modifications to `backend/main.py` or `backend/api/` invalidate only the final layer of the image, allowing rebuilds (`docker compose build backend`) to complete in **under 2 seconds**.

---

## 3. Frontend Multi-Stage Architecture (`Dockerfile.frontend`)

`infrastructure/docker/Dockerfile.frontend` is structured into four stages optimized for React 18 / TypeScript / Vite:

```
[stage: base] (node:20-slim)
      │
      └── Setup workdir /app/frontend & install common tools
      │
      ├─────────────────────────────────────────────┐
      ▼                                             ▼
[stage: dev] (Default target)               [stage: prod-build]
      │                                             │
      ├── Copy package.json & package-lock.json     ├── Copy package.json & npm ci --strict
      ├── Run npm install                           ├── Copy ./src, ./index.html, ./vite.config.ts
      ├── Mount local ./src at runtime              ├── Run tsc && vite build -> /app/frontend/dist
      └── CMD npm run dev (--host 0.0.0.0)          │
                                                    ▼
                                            [stage: prod] (nginx:alpine)
                                                    │
                                                    ├── Copy custom non-root nginx.conf
                                                    ├── Copy /app/frontend/dist -> /usr/share/nginx/html
                                                    └── EXPOSE 80 / CMD nginx -g "daemon off;"
```

---

## 4. Working with Docker Profiles

RAGuard AI organizes optional and specialized services using **Docker Compose Profiles** (`docker compose --profile <name> up -d`).

### 4.1 Profile Directory
| Profile Name | Services Included | Usage Scenario |
| :--- | :--- | :--- |
| **`default` (No profile)** | `postgres`, `redis`, `qdrant`, `backend`, `frontend`, `celery-worker` | Standard daily feature development and testing. |
| **`dev-tools`** | `pgadmin` (Port 5050), `redis-commander` (Port 8081) | Visual database inspection, SQL queries, and queue debugging. |
| **`monitoring`** | `prometheus` (Port 9090), `grafana` (Port 3000), `loki`, `otel-collector` | Performance profiling, distributed trace visualization, and log aggregation. |
| **`test`** | `backend-test` (isolated test DB run), `pytest-runner` | Automated CI verification and regression test suite execution. |

### 4.2 Common Command Examples
```bash
# Start core development stack
docker compose up -d

# Start core stack + visual debugging GUI tools (pgAdmin + Redis Commander)
docker compose --profile dev-tools up -d

# Build and verify production stage locally
docker compose -f docker-compose.yml -f docker-compose.prod.yml build
```

---

## 5. Security Hardening & Container Hygiene

Every container image produced by these Dockerfiles adheres to strict security rules:
1. **Zero Root Processes**: All commands execute under `USER 10001` or `raguard`.
2. **No New Privileges**: `security_opt: [no-new-privileges:true]` blocks setuid binaries from escalating privileges within the container.
3. **Dropped Capabilities**: `cap_drop: [ALL]` strips unused Linux kernel capabilities (e.g. `CAP_SYS_ADMIN`, `CAP_NET_RAW`), preventing host kernel exploits.
4. **Health Check Probing**: Every container defines an explicit health check probe using lightweight internal tools (`pg_isready`, `redis-cli`, `curl` / python HTTP requests) without bloating base images.
