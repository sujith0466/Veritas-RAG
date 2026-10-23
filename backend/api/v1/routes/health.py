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
_startup_complete: bool = False


def _get_uptime_seconds() -> float:
    return time.time() - _START_TIME


def mark_startup_complete() -> None:
    """Mark the application startup phase as complete (called by lifespan)."""
    global _startup_complete
    _startup_complete = True


def reset_startup_state() -> None:
    """Reset the startup state for testing or lifecycle reset."""
    global _startup_complete
    _startup_complete = False


def is_startup_complete() -> bool:
    """Check if the application startup phase has completed."""
    return _startup_complete


# ── GET /health ────────────────────────────────────────────────────────────────


@router.get(
    "",
    response_model=HealthStatus,
    summary="Overall health",
    description="Returns the overall health status of the Veritas RAG service.",
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


# ── GET /health/startup ────────────────────────────────────────────────────────


@router.get(
    "/startup",
    summary="Startup probe",
    description=(
        "Startup probe. Returns 200 once application initialization and startup validations "
        "are complete. Returns 503 while initialization is in progress."
    ),
)
async def startup() -> JSONResponse:
    """Startup probe — returns 200 once application initialization is complete."""
    now_iso = datetime.now(UTC).isoformat()
    if _startup_complete:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "started", "timestamp": now_iso},
        )
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "starting", "timestamp": now_iso},
    )


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

    # 4. LLM Provider & Circuit Breaker Aggregation
    from backend.ai.factory import create_llm_provider
    from backend.ai.interfaces.llm_provider import LLMProvider  # noqa: TC001
    from backend.modules.reliability.circuit_breaker.engine import CircuitBreakerEngine
    from backend.modules.reliability.circuit_breaker.states import CircuitState

    t0 = time.time()
    llm_info = None
    llm_ok = False
    llm_err = None
    provider_status = "healthy"
    provider_states: dict[str, str] = {}

    settings = get_settings()
    priority_list = getattr(settings.ai, "priority_list", []) or []
    cb_engine = CircuitBreakerEngine()

    try:
        for p in priority_list:
            st = await cb_engine.check_state("system", p)
            provider_states[p] = st.value

        if priority_list:
            primary_p = priority_list[0]
            primary_st = provider_states.get(primary_p, CircuitState.CLOSED.value)
            all_open = all(st == CircuitState.OPEN.value for st in provider_states.values())
            any_available = any(st != CircuitState.OPEN.value for st in provider_states.values())

            if all_open:
                provider_status = "unhealthy"
                llm_ok = False
                llm_err = "All configured AI providers have tripped circuit breakers (OPEN)"
            elif primary_st == CircuitState.OPEN.value and any_available:
                provider_status = "degraded"
                llm_ok = True
            else:
                provider_status = "healthy"
                llm_ok = True
        else:
            provider_status = "healthy"
            llm_ok = True

        if llm_ok and provider_status != "degraded":
            try:
                llm: LLMProvider = create_llm_provider()
                llm_ok = await llm.health_check()
                if not llm_ok:
                    provider_status = "unhealthy"
            except Exception as exc:
                llm_err = str(exc)
                llm_ok = False
                provider_status = "unhealthy"

        llm_info = {
            "provider_status": provider_status,
            "circuit_states": provider_states,
        }
    except Exception as exc:
        llm_err = str(exc)
        provider_status = "unhealthy"
        llm_ok = False

    llm_latency = (time.time() - t0) * 1000
    deps["llm_provider"] = DependencyHealth(
        name="llm_provider",
        status=provider_status if (llm_ok or provider_status == "degraded") else "unhealthy",
        latency_ms=round(llm_latency, 2) if llm_ok else None,
        error=llm_err,
        info=llm_info,
    )

    # 5. Embedding Provider Isolation (WP-3D Preflight Guard)
    embedding_provider_name = getattr(settings.embeddings, "default_provider", "openai")
    is_embedding_isolated = embedding_provider_name.lower() in ("local", "mock", "offline")
    deps["embedding_provider"] = DependencyHealth(
        name="embedding_provider",
        status="healthy" if is_embedding_isolated else "degraded",
        latency_ms=0.0,
        error=None if is_embedding_isolated else f"Non-isolated external embedding provider: {embedding_provider_name}",
        info={
            "default_provider": embedding_provider_name,
            "is_isolated": is_embedding_isolated,
            "local_model": getattr(settings.embeddings, "local_model", "all-MiniLM-L6-v2"),
        },
    )

    # 6. Celery Workers
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
        "Returns 200 with degraded status when primary AI provider is OPEN but fallback is available. "
        "Returns 503 when any required dependency or all AI providers are unavailable."
    ),
)
async def readiness() -> JSONResponse:
    """Readiness probe — checks dependency availability and AI provider circuit breaker aggregation."""
    settings = get_settings()
    deps_dict = await _check_dependencies(detailed=False)

    # Core infra dependencies required for readiness
    required_deps = ["postgresql", "redis", "qdrant", "object_storage"]
    is_ready = True
    for req in required_deps:
        if deps_dict.get(req) and deps_dict[req].status not in ("healthy", "not_initialized"):
            is_ready = False
            break

    # AI provider circuit breaker aggregation
    llm_dep = deps_dict.get("llm_provider")
    provider_status = "healthy"
    if llm_dep:
        if llm_dep.status == "unhealthy":
            is_ready = False
            provider_status = "unhealthy"
        elif llm_dep.status == "degraded":
            provider_status = "degraded"
        else:
            provider_status = "healthy"

    overall_status = "ready" if is_ready else "not_ready"
    if is_ready and provider_status == "degraded":
        overall_status = "degraded"

    payload = {
        "status": overall_status,
        "version": settings.app.version,
        "timestamp": datetime.now(UTC).isoformat(),
        "provider_status": provider_status,
        "dependencies": {k: v.status for k, v in deps_dict.items()},
    }

    if not is_ready:
        logger.warning("Readiness check failed", dependencies=payload["dependencies"], provider_status=provider_status)
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
        "Requires PLATFORM_ADMIN role via authentication and authorization dependencies."
    ),
)
async def detailed_health(
    _user: UserContext = Depends(require_role(Role.PLATFORM_ADMIN)),
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
