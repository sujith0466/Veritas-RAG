# Veritas RAG — Developer Onboarding & One-Command Setup Guide

**Document Version**: 1.0.0
**Phase**: Phase 1 — Foundation & Enterprise Setup
**Milestone**: Milestone 5 — Infrastructure & Developer Environment
**Status**: Approved & Frozen Baseline

---

## 1. Welcome to Veritas RAG!

Veritas RAG is built on a strict **Developer Experience Contract**: any new engineer joining the team must be able to clone the repository, run **one single command**, and have the entire enterprise stack (`backend`, `frontend`, `postgres`, `redis`, `qdrant`, `celery-worker`) fully compiled, healthy, migrated, and ready for code changes within 5 minutes.

No manual database installation. No manual Redis setup. No undocumented environment configurations.

---

## 2. Prerequisite Check

Before executing the one-command setup, verify your workstation has the following base engines installed:

| Tool | Minimum Version | Verification Command |
| :--- | :--- | :--- |
| **Docker Engine / Desktop** | `24.0+` | `docker --version` |
| **Docker Compose (v2)** | `v2.20+` | `docker compose version` |
| **Git** | `2.40+` | `git --version` |
| **PowerShell** *(Windows only)*| `5.1+` or `7.x` | `$PSVersionTable.PSVersion` |
| **GNU Make** *(Optional/Linux)*| `4.3+` | `make --version` |

---

## 3. The One-Command Setup Contract

Open your terminal (PowerShell on Windows, or Bash/Zsh on macOS/Linux), navigate to the root of the cloned repository (`d:\Veritas RAG`), and execute your platform's single onboarding command:

### On Windows (PowerShell)
```powershell
./Infrastructure/scripts/bootstrap.ps1
```

### On Linux / macOS / WSL / Git Bash
```bash
make setup   # Or directly: ./Infrastructure/scripts/bootstrap.sh
```

---

## 4. What `bootstrap` Automatically Does for You

When you execute `bootstrap.ps1` or `make setup`, the automation pipeline executes 7 verification and provisioning steps in sequence without requiring input:

1. **Prerequisite Audit**: Confirms Docker Daemon is responsive and required CLI tools are present.
2. **Environment Template Initialization**: Checks if `.env.local` exists. If missing, it securely copies `.env.example` to `.env.local`.
3. **Pre-Flight Environment Validation**: Executes `python infrastructure/env/validate_env.py` to check formatting, port validity, and required configuration strings (`DATABASE_URL`, `SUPABASE_*`).
4. **Multi-Stage Image Compilation**: Runs `docker compose build` across the multi-stage Dockerfiles (`Dockerfile.backend`, `Dockerfile.frontend`).
5. **Orchestrated Container Launch**: Runs `docker compose up -d` using the shared base profile and development overrides.
6. **Health SLA Polling**: Monitors container health endpoints every 3 seconds until `postgres`, `redis`, `qdrant`, `backend`, `frontend`, and `celery-worker` transition to `healthy`.
7. **Database Schema Verification**: Automatically executes `alembic upgrade head` inside the healthy `backend` container to verify all tables and indexes match the current code baseline.

---

## 5. Verifying Your Local Access URLs

Once `bootstrap` completes, your local ecosystem is live at these canonical endpoints:

| Service / Interface | Local URL | Description |
| :--- | :--- | :--- |
| **React UI Application** | `http://localhost:5173` | Hot-reloading Vite dev server serving the frontend SPA. |
| **FastAPI Backend API** | `http://localhost:8000` | Uvicorn server with `--reload` enabled (`/docs` for Swagger UI). |
| **API Liveness Probe** | `http://localhost:8000/api/v1/health/live` | Tier 1 instant liveness probe. |
| **API Readiness Probe** | `http://localhost:8000/api/v1/health/ready`| Tier 2 readiness check verifying database/cache connectivity. |
| **pgAdmin 4 GUI** *(Optional)* | `http://localhost:5050` | Visual PostgreSQL explorer (Email: `admin@veritasrag.ai`, Pass: `admin`). |
| **Redis Commander GUI** *(Optional)*| `http://localhost:8081` | Visual cache and Celery task queue explorer. |

---

## 6. Daily Developer Workflow (`Makefile` & Scripts)

Instead of memorizing long `docker compose` commands, use the standardized root commands:

### Windows PowerShell Commands
```powershell
# Start all containers in background
./Infrastructure/scripts/start.ps1

# Stop all containers and clean up bridge networks
./Infrastructure/scripts/stop.ps1

# Restart containers (e.g. after adding a new requirements/dev.txt package)
./Infrastructure/scripts/restart.ps1

# Stream real-time logs across all services
./Infrastructure/scripts/logs.ps1

# Check three-tier health status across all containers
./Infrastructure/scripts/health.ps1

# Run Alembic schema migration
./Infrastructure/scripts/migrate.ps1

# Wipe all containers, networks, and named volumes to reset to clean slate
./Infrastructure/scripts/reset.ps1
```

### Linux / macOS / WSL (`make` interface)
```bash
make start      # docker compose up -d
make stop       # docker compose down
make restart    # docker compose restart
make logs       # docker compose logs -f
make health     # check health endpoints
make migrate    # alembic upgrade head
make reset      # docker compose down -v && clean data
```

---

## 7. Next Steps & Architecture Guidance

Now that your local environment is live:
1. Review `infrastructure/docs/Infrastructure-contract.md` to understand our three-tier health checks and container security rules.
2. Review `infrastructure/docs/environment-guide.md` to understand how `.env.local` overrides default Pydantic settings.
3. If you encounter port conflicts or volume errors, consult `infrastructure/docs/troubleshooting.md`.
