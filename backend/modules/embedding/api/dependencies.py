"""Embedding API dependencies (`ADR-M2-001`).

Provides FastAPI dependency injection functions for database session repositories,
`EmbeddingService` instantiation, and multi-tenant namespace resolution.
"""

from typing import Any

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.dependencies.auth import get_optional_user
from backend.core.dependencies.database import get_db
from backend.core.events.dispatcher import get_dispatcher
from backend.modules.embedding.repositories.embedding_repository import EmbeddingRepository
from backend.modules.embedding.services.embedding_service import EmbeddingService


def get_embedding_repository(
    session: AsyncSession = Depends(get_db),
) -> EmbeddingRepository:
    """Inject an `EmbeddingRepository` bound to the current request transaction session."""
    return EmbeddingRepository(session)


def get_embedding_service(
    repository: EmbeddingRepository = Depends(get_embedding_repository),
) -> EmbeddingService:
    """Inject an `EmbeddingService` configured with repository and global event dispatcher."""
    return EmbeddingService(repository, event_dispatcher=get_dispatcher())


def resolve_tenant(
    user: Any | None = Depends(get_optional_user),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
) -> str:
    """Resolve active tenant identifier from user session or `X-Tenant-ID` header (`default_tenant` fallback)."""
    if user and getattr(user, "tenant_id", None):
        return user.tenant_id
    return x_tenant_id or "default_tenant"
