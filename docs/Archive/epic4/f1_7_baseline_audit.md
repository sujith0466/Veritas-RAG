# F1.7 CI/CD Foundation — Baseline Audit & Gap Analysis

## 1. Version 1 Baseline Audit
An exhaustive audit of the existing CI/CD capabilities in the `RAGuard` repository was conducted.

### 1.1 Evaluated Components
*   **GitHub Actions Workflows**: `.github/workflows/ci.yml`, `.github/workflows/docker-build.yml`, `.github/workflows/release.yml`
*   **Local Orchestration**: `Makefile`, `infrastructure/scripts/bootstrap.sh`
*   **Dependency Management**: `requirements.txt`, `requirements-lock.txt`, `dependabot.yml`
*   **Code Quality**: `pyproject.toml` (Ruff, Mypy), `.pre-commit-config.yaml`
*   **Artifact Generation**: `infrastructure/docker/` multi-stage Dockerfiles

### 1.2 Current State Observations
*   **Continuous Integration (`ci.yml`)**: Triggers on push to `main/develop` and PRs. It successfully sets up Python 3.13, Postgres, and Redis service containers. It executes Ruff, Mypy, Bandit, and Pytest with coverage. **Gap**: It only validates the backend. It uses `requirements.txt` instead of the reproducible `requirements-lock.txt`. It lacks frontend linting/testing and Node caching.
*   **Docker Build Validation (`docker-build.yml`)**: Extensively tests multi-stage Docker builds across Dev and Production targets for both Frontend and Backend, utilizing GH Actions caching (`cache-from/to`). **Status**: Highly robust, production-ready.
*   **Release Automation (`release.yml`)**: Triggers on tags (`v*.*.*`). It runs tests, builds a Docker image, and creates a GitHub Release. **Gap**: It does not push the generated Docker artifact to a container registry (e.g., GHCR or Docker Hub).
*   **Deployment Workflows**: **Gap**: No pipeline exists for staging auto-deployment upon merging to `main`.
*   **Security Scanning**: Bandit (SAST) and detect-secrets (pre-commit) are present. Dependabot is correctly configured for pip, npm, and docker weekly scans.
*   **Branch Protection Assumptions**: CI relies on PR checks passing before merge. 

---

## 2. Gap Analysis

| Component | Current State | Required State | Recommendation | Target Task |
| :--- | :--- | :--- | :--- | :--- |
| **Backend CI Pipeline** | Validates via `requirements.txt` | Must use `requirements-lock.txt` for reproducibility | ⬆ Improve | Update `ci.yml` pip install command |
| **Frontend CI Pipeline** | Missing | Validate TS/React via ESLint and Vite build | 🆕 Implement New | Add `frontend-test` job to `ci.yml` with `npm` caching |
| **Docker Build Pipeline** | Multi-stage build testing with caching | Maintain | ✅ Reuse As-Is | — |
| **Release Pipeline** | Builds image but drops it | Must push tagged image to GHCR | ⬆ Improve | Add `docker push` and registry login to `release.yml` |
| **Staging Deployment** | Missing | Auto-deploy to staging environment on merge to `main` | 🆕 Implement New | Create `.github/workflows/deploy-staging.yml` |
| **Local Orchestration** | Makefile & scripts functional | Maintain | ✅ Reuse As-Is | — |
| **Code Quality Configs** | Ruff, Mypy, Bandit functional | Maintain | ✅ Reuse As-Is | — |
| **Dependency Auditing** | Dependabot active | Maintain | ✅ Reuse As-Is | — |
