"""API v1 router — aggregates all domain sub-routers."""

from fastapi import APIRouter

from backend.document.api import router as document_router
from backend.observability.monitoring import router as metrics_router

from .routes.auth import router as auth_router
from .routes.health import router as health_router

api_v1_router = APIRouter()

# ── Health, Readiness & Prometheus Metrics ─────────────────────────────────────
api_v1_router.include_router(health_router)
api_v1_router.include_router(metrics_router)


# ── Authentication & Identity (`/auth`) ─────────────────────────────────────────
api_v1_router.include_router(auth_router)

# ── Document Intelligence Foundation (`/documents`) ────────────────────────────
api_v1_router.include_router(document_router)

# ── Knowledge Layer Foundation (`/chunks`) ─────────────────────────────────────
from backend.modules.chunking.api import router as chunk_router

api_v1_router.include_router(chunk_router)

# ── Embedding Pipeline (`/embeddings`) ─────────────────────────────────────────
from backend.modules.embedding.api import router as embedding_router

api_v1_router.include_router(embedding_router)

# ── Vector Storage Foundation (`/vectors`) ─────────────────────────────────────
from backend.modules.vector.api import router as vector_router

api_v1_router.include_router(vector_router)

# ── Hybrid Retrieval Engine (`/retrieval`) ─────────────────────────────────────
from backend.modules.retrieval.api import router as retrieval_router

api_v1_router.include_router(retrieval_router)

# ── Retrieval Reliability Framework (`/reliability`) ───────────────────────────
from backend.modules.reliability.api import reliability_router

api_v1_router.include_router(reliability_router)

# ── Knowledge Health & Lifecycle Management (`/knowledge-health`) ──────────────
from backend.modules.knowledge_health.api import \
    router as knowledge_health_router

api_v1_router.include_router(knowledge_health_router, prefix="/knowledge-health")

# ── Query Analytics & Reliability Intelligence (`/analytics`) ──────────────────
from backend.modules.analytics.api import router as analytics_router

api_v1_router.include_router(analytics_router, prefix="/analytics")

# ── Executive & Knowledge Intelligence Dashboard (`/dashboard`) ────────────────
from backend.modules.dashboard.api import router as dashboard_router

api_v1_router.include_router(dashboard_router, prefix="/dashboard")

# ── AI Chat & Persistence (`/chat`) ────────────────────────────────────────────
from backend.modules.chat.api import router as chat_router

api_v1_router.include_router(chat_router)
