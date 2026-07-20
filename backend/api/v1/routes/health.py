"""Health and readiness check endpoints.

Provides four health endpoints for different observability consumers:

GET /health         — Overall health (used by load balancers and dashboards)
GET /health/live    — Liveness probe (Kubernetes: is the process alive?)
GET /health/ready   — Readiness probe (Kubernetes: can it serve traffic?)
GET /health/detailed — Admin-only full dependency breakdown

Liveness vs Readiness:
- Liveness: always returns 200 if the process is running. A failure here
  causes the orchestrator to restart the container.
- Readiness: returns 503 if any required dependency (DB, cache) is unavailable.
  A failure here removes the pod from the load balancer without restarting it.
"""

from datetime import UTC, datetime
import time
from typing import Any

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
import structlog

from backend.core.auth.context import UserContext
from backend.core.config import get_settings
from backend.core.dependencies.auth import require_role
from backend.core.permissions.rbac import Role

from ..schemas.common import DependencyHealth, DetailedHealthResponse, HealthStatus

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/health", tags=["Health"])

_START_TIME = time.time()


def _get_uptime_seconds() -> float:
    return time.time() - _START_TIME


# ── GET /health ────────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=HealthStatus,
    summary="Overall health",
    description="Returns the overall health status of the RAGuard AI service.",
)
async def health() -> HealthStatus:
    """Overall health endpoint — suitable for load balancer health checks."""
    settings = get_settings()
    return HealthStatus(
        status="healthy",
        version=settings.app.version,
        environment=settings.app.environment,
    )


# ── GET /health/live ───────────────────────────────────────────────────────────

@router.get(
    "/live",
    summary="Liveness probe",
    description=(
        "Liveness probe. Returns 200 as long as the process is running. "
        "A failure causes the container orchestrator to restart the pod."
    ),
)
async def liveness() -> dict[str, Any]:
    """Liveness probe — always 200 if the process is alive."""
    return {
        "status": "alive",
        "uptime_seconds": round(_get_uptime_seconds(), 2),
        "timestamp": datetime.now(UTC).isoformat(),
    }


async def _check_dependencies() -> dict[str, str]:
    """Ping downstream infrastructure dependencies."""
    from backend.cache.client import check_cache_health
    from backend.database.engine import check_db_health
    from backend.vector_db.client import check_vector_db_health

    db_ok = await check_db_health()
    cache_ok = await check_cache_health()
    vector_ok = await check_vector_db_health()

    return {
        "postgresql": "healthy" if db_ok else "unhealthy",
        "redis": "healthy" if cache_ok else "unhealthy",
        "qdrant": "healthy" if vector_ok else "unhealthy",
    }


# ── GET /health/ready ──────────────────────────────────────────────────────────

@router.get(
    "/ready",
    summary="Readiness probe",
    description=(
        "Readiness probe. Returns 200 when all required dependencies are available. "
        "Returns 503 when any required dependency (database, cache) is unavailable. "
        "A 503 removes this instance from the load balancer rotation."
    ),
)
async def readiness() -> JSONResponse:
    """Readiness probe — checks dependency availability."""
    settings = get_settings()
    dependencies = await _check_dependencies()

    # All dependencies must be healthy (or not_initialized in M1)
    # In M2, change "not_initialized" checks to real health checks
    is_ready = all(
        v in ("healthy", "not_initialized") for v in dependencies.values()
    )

    payload = {
        "status": "ready" if is_ready else "not_ready",
        "version": settings.app.version,
        "timestamp": datetime.now(UTC).isoformat(),
        "dependencies": dependencies,
    }

    if not is_ready:
        logger.warning("Readiness check failed", dependencies=dependencies)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=payload,
        )

    return JSONResponse(status_code=status.HTTP_200_OK, content=payload)


# ── GET /health/detailed ───────────────────────────────────────────────────────

@router.get(
    "/detailed",
    response_model=DetailedHealthResponse,
    summary="Detailed health (admin)",
    description=(
        "Full dependency health breakdown. "
        "Requires ADMIN role via authentication and authorization dependencies."
    ),
)
async def detailed_health(
    _user: UserContext = Depends(require_role(Role.ADMIN)),
) -> DetailedHealthResponse:
    """Full dependency breakdown for operator dashboards."""
    settings = get_settings()
    deps_dict = await _check_dependencies()
    deps = [DependencyHealth(name=k, status=v) for k, v in deps_dict.items()]

    statuses = {d.status for d in deps}
    if "unhealthy" in statuses:
        overall = "unhealthy"
    elif "not_initialized" in statuses:
        overall = "degraded"
    else:
        overall = "healthy"

    return DetailedHealthResponse(
        status=overall,
        version=settings.app.version,
        environment=settings.app.environment,
        dependencies=deps,
    )
