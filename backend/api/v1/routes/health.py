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

import time
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from backend.core.auth.context import UserContext
from backend.core.config import get_settings
from backend.core.dependencies.auth import require_role
from backend.core.permissions.rbac import Role

from ..schemas.common import (DependencyHealth, DetailedHealthResponse,
                              HealthStatus)

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


async def _check_dependencies(detailed: bool = False) -> dict[str, DependencyHealth]:
    """Ping downstream infrastructure dependencies."""
    from backend.cache.client import check_cache_health, get_redis_client
    from backend.database.engine import check_db_health
    from backend.vector_db.client import check_vector_db_health, get_qdrant_client
    from backend.core.config.llm_manager import LLMManagerSettings
    from backend.tasks.celery_app import celery_app
    import uuid
    import asyncio
    
    settings = get_settings()
    
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
    cache_ok = await check_cache_health()
    cache_latency = (time.time() - t0) * 1000
    
    redis_info = None
    if detailed and cache_ok:
        try:
            # Audit background queues
            redis = get_redis_client()
            # Celery uses lists or sets for queues. We can get lengths.
            # In Celery, queues are lists named after the queue. Default is 'celery' but we defined 'default', 'ingestion', etc.
            queue_info = {}
            for q in ["default", "ingestion", "embeddings", "retrieval", "evaluation", "health", "ai"]:
                length = await redis.llen(q)
                if length > 0:
                    queue_info[q] = length
            
            # Simple queue stats
            redis_info = {
                "queue_lengths": queue_info,
            }
        except Exception as e:
            logger.error(f"Error fetching redis info: {e}")

    deps["redis"] = DependencyHealth(
        name="redis",
        status="healthy" if cache_ok else "unhealthy",
        latency_ms=round(cache_latency, 2) if cache_ok else None,
        error=None if cache_ok else "Redis connection failed",
        info=redis_info
    )

    # 3. Qdrant
    t0 = time.time()
    qdrant_info = None
    vector_ok = False
    vector_err = None
    try:
        qclient = get_qdrant_client()
        cols = await qclient.get_collections()
        vector_ok = True
        
        if detailed:
            # Collection Exists, Collection Count, Access, Search Test
            col_count = len(cols.collections)
            # Find the main collection if any
            test_success = False
            if col_count > 0:
                try:
                    # Simple search test on first collection
                    await qclient.search(
                        collection_name=cols.collections[0].name,
                        query_vector=[0.0] * 384, # dummy vector, might fail if dimension mismatch, so we just use scroll
                        limit=1
                    )
                    test_success = True
                except Exception:
                    try:
                        await qclient.scroll(collection_name=cols.collections[0].name, limit=1)
                        test_success = True
                    except Exception:
                        pass
            
            qdrant_info = {
                "collection_count": col_count,
                "collections_exist": col_count > 0,
                "search_test": test_success
            }
    except Exception as exc:
        vector_err = str(exc)
        logger.warning("Qdrant health check failed", error=str(exc))
    
    qdrant_latency = (time.time() - t0) * 1000
    
    deps["qdrant"] = DependencyHealth(
        name="qdrant",
        status="healthy" if vector_ok else "unhealthy",
        latency_ms=round(qdrant_latency, 2) if vector_ok else None,
        error=vector_err,
        info=qdrant_info
    )

    # 4. LLM Provider
    # Lazy import to avoid circular dependencies
    from backend.ai.factory import create_llm_provider
    from backend.ai.interfaces.llm_provider import LLMProvider
    
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
        except Exception as exc:
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

    # PostgreSQL, Redis, Qdrant must be healthy for readiness
    required_deps = ["postgresql", "redis", "qdrant"]
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
