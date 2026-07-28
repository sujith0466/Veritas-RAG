"""RAGuard AI domain and persistence models."""

from typing import Any

from .base import BaseModel
from .entities.audit_log import AuditLog
from .entities.user import User

__all__ = [
    "AuditLog",
    "BaseModel",
    "ChatMessage",
    "ChatSession",
    "ChunkEmbedding",
    "ChunkRelationship",
    "CircuitBreakerEventLog",
    "Document",
    "DocumentChunk",
    "DocumentEventLog",
    "DocumentVersion",
    "EmbeddingJob",
    "HealthScanJob",
    "LLMAuditRecord",
    "ProcessingJob",
    "QueryAnalyticsRecord",
    "RetrievalQueryLog",
    "RetrievalSLALog",
    "StaleEmbeddingRecord",
    "StorageObject",
    "User",
    "VectorIndexMetadata",
]


def __getattr__(name: str) -> Any:
    if name in {
        "Document",
        "DocumentEventLog",
        "DocumentVersion",
        "ProcessingJob",
        "StorageObject",
    }:
        import backend.document.models as doc_models

        return getattr(doc_models, name)
    if name in {"DocumentChunk", "ChunkRelationship"}:
        import backend.modules.chunking.models as chunk_models

        return getattr(chunk_models, name)
    if name in {"ChunkEmbedding", "EmbeddingJob"}:
        import backend.modules.embedding.models as emb_models

        return getattr(emb_models, name)
    if name in {"VectorIndexMetadata"}:
        import backend.modules.vector.models as vec_models

        return getattr(vec_models, name)
    if name in {"RetrievalQueryLog"}:
        import backend.modules.retrieval.models as ret_models

        return getattr(ret_models, name)
    if name in {"RetrievalSLALog", "CircuitBreakerEventLog"}:
        import backend.modules.reliability.models as rel_models

        return getattr(rel_models, name)
    if name in {"HealthScanJob", "StaleEmbeddingRecord"}:
        import backend.modules.knowledge_health.models as kh_models

        return getattr(kh_models, name)
    if name in {"QueryAnalyticsRecord"}:
        import backend.modules.analytics.models as anl_models

        return getattr(anl_models, name)
    if name in {"LLMAuditRecord"}:
        import backend.modules.generation.models as gen_models

        return getattr(gen_models, name)
    if name in {"ChatSession", "ChatMessage"}:
        import backend.modules.chat.models as chat_models

        return getattr(chat_models, name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
