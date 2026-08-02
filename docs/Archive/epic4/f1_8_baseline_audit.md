# F1.8 Cloud Infrastructure Foundation — Baseline Audit & Gap Analysis

## 1. Version 1 Baseline Audit
A comprehensive audit of the `RAGuard` cloud infrastructure, deployment models, and environment definitions was conducted.

### 1.1 Evaluated Components
*   **Container Orchestration (Local)**: `docker-compose.yml` and `docker-compose.prod.yml`
*   **Kubernetes Manifests**: `infrastructure/kubernetes/*`
*   **Infrastructure as Code (IaC)**: `infrastructure/terraform/*`
*   **Reverse Proxy**: `infrastructure/nginx/` and `deploy/nginx/`
*   **Databases & Storage**: PostgreSQL, Redis, Qdrant, MinIO (as defined in Compose)
*   **Observability integration**: Prometheus, Jaeger.

### 1.2 Current State Observations
*   **Docker Architecture**: Multi-stage Dockerfiles (`Dockerfile.backend`, `Dockerfile.frontend`) are robust and optimized. `docker-compose.yml` handles orchestration effectively for local development with strict dependency ordering and health checks.
*   **Resource Constraints**: `docker-compose.yml` lacks CPU and Memory limits/requests. This poses a risk of noisy-neighbor issues during local stress testing or lightweight swarm deployments.
*   **Kubernetes (K8s)**: The directory structure exists (`deployments`, `services`, `ingress`, `hpa`, etc.), but the directories are **empty**. There are no foundational YAML manifests or Helm charts defined.
*   **Terraform (IaC)**: The module structure (`compute`, `networking`, `storage`, `iam`) and environment folders (`dev`, `staging`, `production`) exist, but they are **empty**.
*   **TLS & Proxying**: `docker-compose.prod.yml` spins up an Nginx container linking to `nginx.conf` and `certs`, establishing a reverse proxy, but a standardized TLS termination configuration for K8s Ingress is missing.
*   **Backup & Disaster Recovery**: The system relies purely on volume persistence (`postgres_data`, `redis_data`). Automated snapshot/cron-based backup mechanisms are absent.

---

## 2. Gap Analysis

| Component | Current State | Required State | Recommendation | Target Task |
| :--- | :--- | :--- | :--- | :--- |
| **Container Resource Limits** | No bounds on CPU/Memory | Explicit limits/reservations defined to prevent resource starvation | ⬆ Improve | Add `deploy.resources` to all services in `docker-compose.yml` |
| **Kubernetes Core Manifests** | Empty directories | Baseline standard Deployments, Services, ConfigMaps, and Secrets for `api`, `worker`, `frontend`, and dependencies | 🆕 Implement New | Populate `infrastructure/kubernetes/` with standard YAML templates |
| **Terraform IaC Base** | Empty directories | Cloud-agnostic (or AWS-targeted) skeletal configurations (`main.tf`, `variables.tf`, `outputs.tf`) for EKS, RDS, S3 | 🆕 Implement New | Populate `infrastructure/terraform/` modules |
| **Disaster Recovery (Backups)** | None | Kubernetes CronJobs for periodic database dumps (PostgreSQL) and volume snapshots | 🆕 Implement New | Create `infrastructure/kubernetes/cronjobs/backup-db.yaml` |
| **Reverse Proxy / Ingress** | Nginx Config via Volume | Kubernetes standard Ingress with TLS annotations (cert-manager) | 🆕 Implement New | Create `ingress/main-ingress.yaml` |
| **Environment Management** | `.env` file | Kubernetes Secrets and ConfigMaps strategy | 🆕 Implement New | Draft secrets management architecture |
