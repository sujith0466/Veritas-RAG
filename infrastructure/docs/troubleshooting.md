# RAGuard AI — Infrastructure Troubleshooting & Incident Guide

**Document Version**: 1.0.0  
**Phase**: Phase 1 — Foundation & Enterprise Setup  
**Milestone**: Milestone 5 — Infrastructure & Developer Environment  
**Status**: Approved & Frozen Baseline  

---

## 1. Overview & Common Failure Modes

When running multi-container stacks across Windows PowerShell, Linux, or macOS, developers may encounter port collisions, volume permission locks, or health check timeouts. This diagnostic guide provides concrete, copy-paste resolutions for every infrastructure failure mode.

---

## 2. Port Collisions (`Address already in use`)

### Symptom
When running `make start` (`docker compose up -d`), Docker exits with:
```
Error response from daemon: driver failed programming external connectivity on endpoint raguard-postgres: Error starting userland proxy: listen tcp4 0.0.0.0:5432: bind: address already in use
```

### Root Cause
Another local service (e.g. local PostgreSQL server, local Redis instance, or an orphan Docker container) is already bound to host port `5432`, `6379`, `8000`, `5173`, or `6333`.

### Resolution Steps
1. **Identify the conflicting host process**:
   ```powershell
   # Windows PowerShell
   Get-NetTCPConnection -LocalPort 5432 | Select-Object LocalAddress,LocalPort,State,OwningProcess
   Get-Process -Id <OwningProcess>

   # Linux / macOS
   lsof -i :5432
   ```
2. **Option A: Stop the conflicting local service**:
   ```powershell
   # Windows PowerShell (Stop local PostgreSQL service)
   Stop-Service postgresql-x64-16
   ```
3. **Option B: Remap host ports in `.env.local`**:
   If you must keep your local PostgreSQL running, override the host port mapping in `.env.local` without changing the internal `raguard-network` port:
   ```env
   # .env.local
   SERVER_PORT=8001
   POSTGRES_HOST_PORT=5433
   REDIS_HOST_PORT=6380
   ```

---

## 3. Container Health Check Failures (`unhealthy` State)

### Symptom
`docker compose ps` reports one or more containers in `(unhealthy)` state, and `backend` remains in `(waiting)` or `(restarting)`:
```
NAME               STATUS                     PORTS
raguard-postgres   Up 25 seconds (unhealthy)  0.0.0.0:5432->5432/tcp
raguard-backend    Up 10 seconds (waiting)    0.0.0.0:8000->8000/tcp
```

### Root Cause & Diagnostics
1. **Inspect specific health probe exit code and output**:
   ```bash
   # Windows PowerShell / Bash
   docker inspect --format="{{json .State.Health}}" raguard-postgres | jq .
   ```
2. **Scenario: Incorrect database credentials or volume corruptions**:
   If `pg_isready` reports `FATAL: password authentication failed for user "postgres"`, the named volume `postgres-data` was created with an old password before `.env.local` was updated.
3. **Resolution: Reset data volume cleanly**:
   ```bash
   ./infrastructure/scripts/reset.ps1   # or make reset
   ./infrastructure/scripts/bootstrap.ps1 # or make setup
   ```

---

## 4. Volume Permissions & Windows Line Ending Issues (`CRLF` vs `LF`)

### Symptom
When starting `backend` or `frontend` containers on Windows, Uvicorn or Vite crashes immediately with:
```
/bin/sh: ^M: bad interpreter: No such file or directory
```
or volume permission errors:
```
PermissionError: [Errno 13] Permission denied: '/app/backend/__pycache__'
```

### Root Cause
1. **Line Endings**: Git checked out shell scripts or Docker entrypoints with Windows `CRLF` (`\r\n`) line breaks instead of Unix `LF` (`\n`).
2. **Volume Permissions**: When mounting host directories (`./backend:/app/backend`) under non-root container users (`UID 10001`), the host filesystem permissions may reject write attempts from inside the Linux container.

### Resolution Steps
1. **Fix Git Line Ending Configuration**:
   Ensure `.gitattributes` at repository root forces `LF` for all shell scripts and Docker files:
   ```gitattributes
   *.sh text eol=lf
   *.py text eol=lf
   Dockerfile* text eol=lf
   ```
   Normalize existing files:
   ```powershell
   git add --renormalize .
   ```
2. **Fix Volume Ownership Inside Container**:
   If host volume mounts block writes, run the cleanup script or temporarily fix directory ownership inside the volume:
   ```bash
   docker compose exec -u root backend chown -R 10001:10001 /app/backend
   ```

---

## 5. Alembic Migration Lock / Divergent History

### Symptom
Running `./infrastructure/scripts/migrate.ps1` (`make migrate`) outputs:
```
alembic.util.exc.CommandError: Can't locate revision identified by 'xxxxxx'
```

### Root Cause
The database `alembic_version` table references a migration hash that no longer exists in `backend/database/migrations/versions/` due to a git branch switch or rebase.

### Resolution Steps
1. **Verify current revision against available scripts**:
   ```bash
   docker compose exec backend alembic current
   docker compose exec backend alembic history
   ```
2. **Option A: Stamp database to head (If schema matches code)**:
   ```bash
   docker compose exec backend alembic stamp head
   ```
3. **Option B: Reset database and re-migrate from scratch**:
   ```bash
   ./infrastructure/scripts/reset.ps1
   ./infrastructure/scripts/bootstrap.ps1
   ```
