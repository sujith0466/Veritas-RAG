"""RAGuard AI — Application Factory.

The create_app() function is the single entry point for constructing the
FastAPI application. It is responsible for:

1. Loading and validating configuration
2. Configuring structured logging
3. Registering all middleware (in correct order)
4. Registering all exception handlers
5. Mounting all API routers
6. Setting up lifespan events (infrastructure client initialization)

The application is constructed via a factory function (rather than a module-level
instance) so that it can be constructed fresh for each test run, preventing state
leakage between tests.

Usage:
    # ASGI entry point (uvicorn / gunicorn)
    app = create_app()

    # Tests
    from fastapi.testclient import TestClient
    client = TestClient(create_app())
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.core.config import get_settings
from backend.core.events import get_dispatcher
from backend.core.exceptions import get_exception_handlers
from backend.core.logging import RequestLoggingMiddleware, configure_logging
from backend.core.middleware import (CorrelationIDMiddleware,
                                     ObservabilityMiddleware,
                                     SecurityHeadersMiddleware)
from backend.observability.tracing import init_tracer

logger = structlog.get_logger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifespan — startup and shutdown events.

    Startup:
    - Log configuration summary
    - Initialize OpenTelemetry tracer
    - (M2) Initialize database connection pool
    - (M2) Initialize Redis client
    - (M2) Initialize Qdrant client
    - Publish SYSTEM_STARTUP_COMPLETED event

    Shutdown:
    - Publish SYSTEM_SHUTDOWN_INITIATED event
    - (M2) Close database connection pool
    - (M2) Close Redis connection
    """
    settings = get_settings()
    dispatcher = get_dispatcher()

    # ── STARTUP ────────────────────────────────────────────────────────────────
    logger.info(
        "RAGuard AI starting",
        app_name=settings.app.name,
        version=settings.app.version,
        environment=settings.app.environment,
        debug=settings.app.debug,
    )

    init_tracer(app_name=settings.app.name, environment=settings.app.environment)

    from backend.cache.client import close_cache, get_redis_pool
    from backend.database.engine import close_db
    from backend.database.init_db import init_db
    from backend.vector_db.client import close_vector_db, get_qdrant_client

    logger.info("Initializing infrastructure clients (PostgreSQL, Redis, Qdrant)")
    await init_db()
    get_redis_pool()
    get_qdrant_client()

    logger.info(
        "Feature flags",
        retry_engine=settings.features.enable_retry_engine,
        reflection=settings.features.enable_reflection,
        evaluation=settings.features.enable_evaluation,
        analytics=settings.features.enable_analytics,
    )

    # Publish startup event so any registered handlers can react
    from backend.core.auth.seed import seed_demo_user

    await seed_demo_user()

    # NOTE: EventDispatcher is initialized and handlers can be registered here.
    logger.info("RAGuard AI startup complete ✓")

    yield  # Application is running

    # ── SHUTDOWN ───────────────────────────────────────────────────────────────
    logger.info("RAGuard AI shutting down")

    logger.info("Closing infrastructure connections")
    await close_db()
    await close_cache()
    await close_vector_db()

    logger.info("RAGuard AI shutdown complete")


# ── Application Factory ────────────────────────────────────────────────────────


def create_app() -> FastAPI:
    """Construct and return the fully configured FastAPI application.

    Returns:
        A FastAPI application instance ready to serve requests.
    """
    settings = get_settings()

    # ── 1. Configure logging (must be first) ─────────────────────────────────
    configure_logging(
        log_level=settings.logging.level,
        log_format=settings.logging.format,
    )

    # ── 2. Create FastAPI instance ────────────────────────────────────────────
    app = FastAPI(
        title=settings.app.name,
        description=(
            "Enterprise Self-Correcting RAG Reliability Platform. "
            "Detects insufficient or conflicting context, performs intelligent "
            "self-correction, validates generated answers, and assigns explainable "
            "reliability scores."
        ),
        version=settings.app.version,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ── 3. Register exception handlers ───────────────────────────────────────
    for exc_class, handler in get_exception_handlers():
        app.add_exception_handler(exc_class, handler)

    # ── 4. Register middleware (LIFO — last registered = first executed) ──────
    # Order of execution on request:
    #   CorrelationID → Observability → SecurityHeaders → CORS → RequestLogging → Route handler

    # Request/response logging (innermost — has access to correlation ID)
    app.add_middleware(
        RequestLoggingMiddleware,
        log_requests=settings.logging.log_requests,
    )

    # CORS — must be before security headers to handle preflight correctly
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.security.cors_origins,
        allow_credentials=settings.security.cors_allow_credentials,
        allow_methods=settings.security.cors_allow_methods,
        allow_headers=settings.security.cors_allow_headers,
    )

    # Security response headers
    app.add_middleware(
        SecurityHeadersMiddleware,
        is_production=settings.app.is_production,
    )

    # Observability metrics and OpenTelemetry span (runs inside CorrelationID)
    app.add_middleware(ObservabilityMiddleware)

    # Correlation ID (outermost — must run before everything else)
    app.add_middleware(CorrelationIDMiddleware)

    # ── 5. Mount API routers ──────────────────────────────────────────────────
    _register_routes(app)

    return app


def _register_routes(app: FastAPI) -> None:
    """Mount all API version routers and root telemetry onto the application."""
    from backend.api.v1.router import api_v1_router
    from backend.api.v1.routes.health import router as health_router
    from backend.observability.monitoring import router as metrics_router

    app.include_router(health_router)
    app.include_router(api_v1_router, prefix="/api/v1")
    app.include_router(metrics_router)

    from backend.core.landing import router as landing_router

    app.include_router(landing_router)

    from fastapi.responses import Response

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        return Response(status_code=204)


# Expose app for ASGI servers (e.g. uvicorn backend.main:app)
app = create_app()
