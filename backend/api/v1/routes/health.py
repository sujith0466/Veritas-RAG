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


async def _check_dependencies(detailed: bool = False) -> dict[str, DependencyHealth]:  # noqa: PLR0915
    """Ping downstream infrastructure dependencies."""
    import asyncio

    from backend.cache.client import check_cache_health, get_redis_client
    from backend.database.engine import check_db_health
    from backend.document.storage.utils import check_storage_health
    from backend.tasks.celery_app import celery_app
    from backend.vector_db.client import check_vector_db_health

    deps = {}

    # 1. PostgreSQL
    t0 = time.time()
    db_ok = await check_db_health()
    db_latency = (time.time() - t0) * 1000
    deps["postgresql"] = DependencyHealth(
        name="postgresql",
        status="healthy" if db_ok else "unhealthy",
        latency_ms=round(db_latency, 2) if db_ok else None,
        error=None if db_ok else "Database connection failed"
    )

    # 2. Redis & Queue Health
    t0 = time.time()
    cache_res = await check_cache_health()
    is_cache_healthy = cache_res.get("status") == "healthy"

    redis_info = cache_res
    if detailed and is_cache_healthy:
        try:
            # Audit background queues
            redis = get_redis_client()
            queue_info = {}
            for q in ["default", "ingestion", "embeddings", "retrieval", "evaluation", "health", "ai"]:
                length = await redis.llen(q)
                if length > 0:
                    queue_info[q] = length
            redis_info["queue_lengths"] = queue_info
        except Exception as e:
            logger.error(f"Error fetching redis queue info: {e}")

    deps["redis"] = DependencyHealth(
        name="redis",
        status="healthy" if is_cache_healthy else "unhealthy",
        latency_ms=cache_res.get("latency_ms"),
        error=cache_res.get("error"),
        info=redis_info
    )

    # 3. Qdrant
    t0 = time.time()
    vector_res = await check_vector_db_health()
    is_vector_healthy = vector_res.get("status") == "healthy"

    deps["qdrant"] = DependencyHealth(
        name="qdrant",
        status="healthy" if is_vector_healthy else "unhealthy",
        latency_ms=vector_res.get("latency_ms"),
        error=vector_res.get("error"),
        info=vector_res
    )

    # 4. Object Storage (F1.5)
    t0 = time.time()
    storage_res = await check_storage_health()
    is_storage_healthy = storage_res.get("status") == "healthy"

    deps["object_storage"] = DependencyHealth(
        name="object_storage",
        status="healthy" if is_storage_healthy else "unhealthy",
        latency_ms=storage_res.get("latency_ms"),
        error=storage_res.get("error"),
        info=storage_res
    )

    # 4. LLM Provider
    # Lazy import to avoid circular dependencies
    from backend.ai.factory import create_llm_provider
    from backend.ai.interfaces.llm_provider import LLMProvider  # noqa: TC001

    t0 = time.time()
    llm_info = None
    llm_ok = False
    llm_err = None
    try:
        # get_llm_provider returns the configured provider
        llm: LLMProvider = create_llm_provider()
        llm_ok = await llm.health_check()
        if detailed:
            # Get class name as provider name
            llm_info = {
                "provider_name": llm.__class__.__name__
            }
    except Exception as exc:
        llm_err = str(exc)

    llm_latency = (time.time() - t0) * 1000
    deps["llm_provider"] = DependencyHealth(
        name="llm_provider",
        status="healthy" if llm_ok else "unhealthy",
        latency_ms=round(llm_latency, 2) if llm_ok else None,
        error=llm_err,
        info=llm_info
    )

    # 5. Celery Workers
    if detailed:
        t0 = time.time()
        celery_info = None
        celery_ok = False
        try:
            # Send ping to workers with a small timeout
            # Celery app.control.ping() is synchronous, so we run in executor
            loop = asyncio.get_running_loop()
            ping_res = await loop.run_in_executor(None, lambda: celery_app.control.ping(timeout=1.0))

            num_active = len(ping_res)
            celery_ok = num_active > 0

            celery_info = {
                "active_workers": num_active,
                "last_successful_ping": datetime.now(UTC).isoformat() if celery_ok else None,
                "ping_responses": ping_res
            }
        except Exception:
            pass

        celery_latency = (time.time() - t0) * 1000
        deps["celery_workers"] = DependencyHealth(
            name="celery_workers",
            status="healthy" if celery_ok else "degraded",  # Not critical for readiness, maybe degraded
            latency_ms=round(celery_latency, 2),
            info=celery_info
        )

    return deps


# ── GET /health/ready ──────────────────────────────────────────────────────────


@router.get(
    "/ready",
    summary="Readiness probe",
    description=(
        "Readiness probe. Returns 200 when all required dependencies are available. "
        "Returns 503 when any required dependency (database, cache, qdrant) is unavailable. "
        "A 503 removes this instance from the load balancer rotation."
    ),
)
async def readiness() -> JSONResponse:
    """Readiness probe — checks dependency availability."""
    settings = get_settings()
    deps_dict = await _check_dependencies(detailed=False)

    # PostgreSQL, Redis, Qdrant, Object Storage must be healthy for readiness
    required_deps = ["postgresql", "redis", "qdrant", "object_storage"]
    is_ready = True
    for req in required_deps:
        if deps_dict.get(req) and deps_dict[req].status not in ("healthy", "not_initialized"):
            is_ready = False
            break

    payload = {
        "status": "ready" if is_ready else "not_ready",
        "version": settings.app.version,
        "timestamp": datetime.now(UTC).isoformat(),
        "dependencies": {k: v.status for k, v in deps_dict.items()},
    }

    if not is_ready:
        logger.warning("Readiness check failed", dependencies=payload["dependencies"])
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
    deps_dict = await _check_dependencies(detailed=True)
    deps = list(deps_dict.values())

    statuses = {d.status for d in deps}
    if "unhealthy" in statuses:
        overall = "unhealthy"
    elif "degraded" in statuses or "not_initialized" in statuses:
        overall = "degraded"
    else:
        overall = "healthy"

    return DetailedHealthResponse(
        status=overall,
        version=settings.app.version,
        environment=settings.app.environment,
        dependencies=deps,
    )
