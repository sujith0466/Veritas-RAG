"""Embedding API dependencies (`ADR-M2-001`).

Provides FastAPI dependency injection functions for database session repositories,
`EmbeddingService` instantiation, and multi-tenant namespace resolution.
"""

from typing import Any

from fastapi import Depends, Header, HTTPException
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
) -> str:
    """Resolve active workspace identifier from user session."""
    if not user or not getattr(user, "workspace_name", None) or user.workspace_name == "None":
        raise HTTPException(status_code=401, detail="Missing workspace context")
    return user.workspace_name
