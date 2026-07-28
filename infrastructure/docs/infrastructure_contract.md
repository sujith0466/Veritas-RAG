# RAGuard AI — Infrastructure Contract & Operational Standards

**Document Version**: 1.0.0  
**Phase**: Phase 1 — Foundation & Enterprise Setup  
**Milestone**: Milestone 5 — Infrastructure & Developer Environment  
**Status**: Approved & Frozen Baseline  

---

## 1. Purpose & Scope

The **Infrastructure Contract** establishes mandatory, non-negotiable standards across all containerized services (`backend`, `frontend`, `postgres`, `redis`, `qdrant`, `celery-worker`, `nginx`) in the RAGuard AI platform. Every service—whether running locally via Docker Compose, in CI/CD pipelines, or deployed to production orchestration clusters (Kubernetes/ECS)—must adhere to these conventions to guarantee reliability, zero-downtime deployments, strict security isolation, and seamless developer onboarding.

---

## 2. Three-Level Health Check Architecture

To support both Docker Compose dependencies and Kubernetes liveness/readiness probes without architectural modifications, all application services must implement a three-tier health probing interface:

### 2.1 Tier 1: Liveness Probe (`GET /api/v1/health/live`)
- **Purpose**: Indicates whether the container process is running and not deadlocked.
- **Behavior**: Returns `200 OK` (`{"status": "live", "timestamp": "..."}`) immediately if the HTTP server can accept sockets and execute event loops. **Must never** check external database or cache connectivity.
- **Docker/K8s Usage**: Used by Kubernetes `livenessProbe` to restart deadlocked or unresponsive pods.

### 2.2 Tier 2: Readiness Probe (`GET /api/v1/health/ready`)
- **Purpose**: Indicates whether the service is ready to receive network traffic and process requests.
- **Behavior**: Verifies that required downstream dependencies (PostgreSQL pool, Redis ping, Qdrant REST API) are accessible. If all dependencies respond within the SLA timeout (2 seconds), returns `200 OK` (`{"status": "ready"}`). If any critical dependency is unreachable, returns `503 Service Unavailable`.
- **Docker/K8s Usage**: Used by Kubernetes `readinessProbe` to remove unready pods from service load balancers, and by Docker Compose `service_healthy` conditions for dependency ordering.

### 2.3 Tier 3: Dependency Health & Detailed Status (`GET /api/v1/health/detailed` & `/api/v1/health`)
- **Purpose**: Provides full diagnostic insight into individual downstream connections, latency metrics, and pool utilization.
- **Behavior**: Returns `200 OK` with granular status (`healthy`, `degraded`, or `unhealthy`) and latency (`ms`) for PostgreSQL, Redis, and Qdrant. Access is restricted to authenticated `ADMIN` roles or internal Docker bridge networks (`localhost` probes).

---

## 3. Container Security Hardening Standards

Every Docker container built and deployed for RAGuard AI must comply with the following defense-in-depth security hardening requirements:

### 3.1 Non-Root Execution (`UID 10001`)
- No application container may run as root (`UID 0`) in production builds.
- Dockerfiles must explicitly create a dedicated system user and group (`raguard:raguard`, `UID 10001`, `GID 10001`) and declare `USER 10001` before the `CMD` or `ENTRYPOINT` instructions.

### 3.2 Privilege Escalation & Capability Dropping
- All container services in `docker-compose.base.yml` and production profiles must enforce:
  ```yaml
  security_opt:
    - no-new-privileges:true
  cap_drop:
    - ALL
  ```
- No container may gain new privileges or retain Linux root capabilities unless explicitly required by low-level networking proxies (and even then, strictly limited to `NET_BIND_SERVICE`).

### 3.3 Read-Only Filesystems & Ephemeral Volumes
- Where feasible, production containers must mount their root filesystem as read-only (`read_only: true`).
- Ephemeral application writes (such as temporary file processing, Python bytecodes, or Uvicorn socket locks) must be directed to isolated `tmpfs` mounts (`/tmp`, `/app/scratch`).

---

## 4. Kubernetes-Compatible Infrastructure Conventions

While Phase 1 orchestration relies on Docker Compose, all definitions follow Kubernetes conventions to ensure zero-refactor migration to Helm charts or K8s manifests in Phase 5+:

1. **Stateless Twelve-Factor Applications**: Application containers (`backend`, `frontend`, `celery-worker`) store zero state on local disk. All persistence is delegated to stateful storage engines (`postgres`, `redis`, `qdrant`).
2. **Graceful Termination Handling**: Containers must intercept `SIGTERM` and `SIGINT` signals cleanly. When `SIGTERM` is received, the application must stop accepting new requests, complete in-flight transactions within a 30-second drain window (`terminationGracePeriodSeconds: 30`), and close database/cache connection pools cleanly.
3. **Configuration Injection via Environment Variables**: All environment-dependent variables (`DATABASE_URL`, `REDIS_HOST`, `QDRANT_HOST`, `SUPABASE_URL`) are injected via ConfigMap/Secret equivalents (`.env.local` / Docker Compose environment maps). No configuration is hardcoded inside container images.
4. **Separation of Config & Secrets**: Sensitive keys (`SUPABASE_JWT_SECRET`, `POSTGRES_PASSWORD`, `OPENROUTER_API_KEY`, `GEMINI_API_KEY`) must never be baked into Docker image layers or committed to Git.

---

## 5. Logging & Observability Contract

1. **Stdout/Stderr Stream Logging**: All containers must emit logs exclusively to standard output (`stdout`) and standard error (`stderr`). Never write application logs to internal log files inside the container filesystem.
2. **Structured JSON Format**: Application services must output structured JSON log entries populated by `structlog` containing at minimum:
   - `timestamp` (ISO 8601 UTC string)
   - `level` (`INFO`, `WARNING`, `ERROR`, `CRITICAL`)
   - `correlation_id` (`X-Correlation-ID` UUID v4 header value for distributed tracing)
   - `service` (`raguard-backend`, `raguard-frontend`, `raguard-worker`)
   - `message` (Human-readable event description)
3. **Log Rotation & Bounding**: Docker Compose driver defaults must limit log size (`max-size: "10m"`, `max-file: "3"`) to prevent local disk exhaustion during intensive background tasks.

---

## 6. Developer Experience Contract (`One-Command Onboarding`)

To eliminate setup friction, any developer onboarding to the repository must achieve a fully functional, tested, and healthy multi-service environment within 5 minutes by executing a single command:

### Windows PowerShell / Linux Bash Contract
```bash
# Windows PowerShell
./Infrastructure/scripts/bootstrap.ps1

# Linux / macOS / WSL / Git Bash
make setup   # or ./Infrastructure/scripts/bootstrap.sh
```

**The Bootstrap script guarantees:**
1. Verifies prerequisite checks (Docker Engine 24+, Docker Compose v2, Git).
2. Copies `.env.example` to `.env.local` if `.env.local` does not exist.
3. Runs `validate_env.py` to ensure all required keys and formatting conform to strict rules.
4. Builds multi-stage development Docker images (`docker compose -f docker-compose.yml -f docker-compose.dev.yml build`).
5. Starts all core services and data engines (`docker compose up -d`).
6. Polls health endpoints until all containers (`postgres`, `redis`, `qdrant`, `backend`, `frontend`, `celery-worker`) transition to `healthy`.
7. Automatically executes Alembic migrations against the healthy database (`alembic upgrade head`).
8. Outputs clear, clickable access URLs (`http://localhost:5173` for UI, `http://localhost:8000/api/v1/health` for API, `http://localhost:5050` for pgAdmin).
