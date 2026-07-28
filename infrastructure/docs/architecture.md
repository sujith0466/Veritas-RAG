# RAGuard AI — Infrastructure Architecture & Service Topology

**Document Version**: 1.0.0  
**Phase**: Phase 1 — Foundation & Enterprise Setup  
**Milestone**: Milestone 5 — Infrastructure & Developer Environment  
**Status**: Approved & Frozen Baseline  

---

## 1. Architectural Overview

The RAGuard AI infrastructure is designed from day one to operate as a distributed, highly resilient microservices and data engine platform. It utilizes strict container boundaries, private internal networking (`raguard-network`), named persistent volumes, and a unified Infrastructure Contract to support seamless local development via Docker Compose while guaranteeing zero-refactor compatibility with Kubernetes and enterprise container platforms.

---

## 2. Service Topology & Container Communication Diagram

```
+--------------------------------------------------------------------------------------------------------------------+
| Private Bridge Network: raguard-network (Isolated Internal DNS & Port Isolation)                                  |
|                                                                                                                    |
|   +--------------------------+          +---------------------------+          +-------------------------------+   |
|   | nginx (Reverse Proxy)    | -------> | frontend (React/Vite Dev) |          | backend (FastAPI Application) |   |
|   | Port: 80 -> Proxy        |          | Port: 5173 / Internal 80  |          | Port: 8000 (Uvicorn --reload) |   |
|   +--------------------------+          +---------------------------+          +-------------------------------+   |
|                                                                                         │                          |
|                                                                     depends_on: healthy │                          |
|                                                                                         ▼                          |
|   +--------------------------+          +---------------------------+          +-------------------------------+   |
|   | postgres (16 Alpine)     |          | redis (7 Alpine)          |          | qdrant (1.12.x Vector Store)  |   |
|   | Port: 5432               |          | Port: 6379                |          | Port: 6333 (REST)/6334 (gRPC) |   |
|   | Vol: postgres-data       |          | Vol: redis-data           |          | Vol: qdrant-data              |   |
|   +--------------------------+          +---------------------------+          +-------------------------------+   |
|                 ▲                                     ▲                                                            |
|                 │                                     │                                                            |
|   +--------------------------+          +---------------------------+                                              |
|   | pgadmin (Dev GUI Profile)|          | celery-worker (Task Engine|                                              |
|   | Port: 5050               |          | Concurrency: 2 / Broker: 1|                                              |
|   +--------------------------+          +---------------------------+                                              |
|                                                       ▲                                                            |
|                                 +---------------------+-----+                                                      |
|                                 | redis-commander (GUI Dev) |                                                      |
|                                 | Port: 8081                |                                                      |
|                                 +---------------------------+                                                      |
+--------------------------------------------------------------------------------------------------------------------+
```

---

## 3. Core Services & Specifications

| Service Name | Docker Image / Build | Port Mappings (Host:Container) | Volume Mounts | Health Check SLA | Role |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`backend`** | `./Infrastructure/docker/Dockerfile.backend` (Target: `dev`) | `8000:8000` | `./backend:/app/backend` (Source code HMR) | `GET /api/v1/health` (Interval: 5s, Retries: 5) | Core ASGI API engine serving domain endpoints & RBAC. |
| **`frontend`** | `./Infrastructure/docker/Dockerfile.frontend` (Target: `dev`) | `5173:5173` | `./frontend:/app/frontend`<br>`anonymous:/app/frontend/node_modules` | `GET /` or `curl localhost:5173` (Interval: 5s) | React 18 + TypeScript + Vite SPA shell. |
| **`celery-worker`**| Shared `Dockerfile.backend` | None (Worker only) | `./backend:/app/backend` | `celery -A backend.tasks.celery_app inspect ping` | Background async execution engine connected to Redis broker. |
| **`postgres`** | `postgres:16-alpine` | `5432:5432` | `postgres-data:/var/lib/postgresql/data` | `pg_isready -U postgres -d raguard` (Interval: 5s) | Relational SQL persistence (users, tenants, audit logs). |
| **`redis`** | `redis:7-alpine` | `6379:6379` | `redis-data:/data` | `redis-cli ping` expecting `PONG` (Interval: 5s) | In-memory cache (`DB 0`), Celery broker (`DB 1`), result store (`DB 2`). |
| **`qdrant`** | `qdrant/qdrant:v1.12.0` | `6333:6333`<br>`6334:6334` | `qdrant-data:/qdrant/storage` | `GET http://localhost:6333/readyz` (Interval: 5s) | High-performance vector database for document embeddings. |
| **`nginx`** | `nginx:alpine` (Optional/Prod) | `80:80` | `./Infrastructure/nginx/default.conf:/etc/nginx/conf.d/default.conf:ro` | `curl -f http://localhost:80` | Reverse proxy load balancer routing `/api/v1` and static assets. |

---

## 4. Volume Strategy & Data Persistence

To prevent data loss while enabling rapid environment resets when required, RAGuard AI separates persistent storage from ephemeral runtime storage using named volumes and anonymous overlays:

### 4.1 Persistent Named Volumes
- **`postgres-data`**: Stores the raw PostgreSQL 16 table schemas, users, indexes, and write-ahead logs (`/var/lib/postgresql/data`).
- **`redis-data`**: Stores persistent snapshot dumps (`dump.rdb`) and AOF logs (`/data`).
- **`qdrant-data`**: Stores vector index segments, payload structures, and collection definitions (`/qdrant/storage`).

### 4.2 Ephemeral & Anonymous Volume Overlays
- **`node_modules` Anonymous Volume (`/app/frontend/node_modules`)**: When mounting the local `./frontend` directory into the frontend container for HMR during development, an anonymous volume is layered over `node_modules`. This prevents host operating system binaries (e.g. Windows native modules) from conflicting with Linux container binaries (`node:20-slim`).
- **`tmpfs` Security Mounts**: Production profiles mount `/tmp` as a `tmpfs` RAM disk to guarantee zero write operations to the base image filesystem.

---

## 5. Network Isolation Architecture

All core application and database containers reside on a single custom bridge network: `raguard-network`.

1. **Internal DNS Resolution**: Containers address each other exclusively via their Docker Compose service names (`postgres`, `redis`, `qdrant`, `backend`, `frontend`). Hardcoding IP addresses (`127.0.0.1` or `192.168.x.x`) inside application code is strictly prohibited.
2. **Port Exposure Rules**:
   - In **Development Profile (`docker-compose.dev.yml`)**: All ports (`8000`, `5173`, `5432`, `6379`, `6333`, `5050`, `8081`) are exposed to `localhost` to allow local IDE debugging, visual database inspection (`pgadmin`), and direct API testing (`curl` / Postman).
   - In **Production Profile (`docker-compose.prod.yml`)**: Only the reverse proxy (`nginx:80/443`) is exposed to the host network. Database (`5432`), cache (`6379`), and vector store (`6333`) ports remain strictly internal to `raguard-network`, blocking all external access attempts.

---

## 6. Three-Level Health Orchestration

The service topology enforces fail-safe startup synchronization:
1. When `./Infrastructure/scripts/start.ps1` (`make start`) is executed, Docker Compose launches `postgres`, `redis`, and `qdrant` concurrently.
2. The `backend` container enters a wait loop supervised by Docker Compose until all three data engines report `status: healthy`.
3. Once `backend` starts Uvicorn and passes its own readiness probe (`GET /api/v1/health/ready`), the `frontend` and `celery-worker` services start, ensuring zero race conditions or connection refusal logs at boot.
