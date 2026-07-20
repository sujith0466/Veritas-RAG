"""Vector Storage API dependencies (`ADR-M3-001`).

Provides FastAPI dependency injection functions for repository access,
`VectorStorageService` instantiation, and multi-tenant namespace resolution (`X-Tenant-ID`).
"""

from typing import Any
from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.dependencies.auth import get_optional_user
from backend.core.dependencies.database import get_db
from backend.core.events.dispatcher import get_dispatcher
from backend.modules.vector.repositories.vector_repository import VectorMetadataRepository
from backend.modules.vector.services.vector_service import VectorStorageService


def resolve_tenant(
    user: Any | None = Depends(get_optional_user),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
) -> str:
    """Resolve active tenant identifier from user session or `X-Tenant-ID` header (`default_tenant` fallback)."""
    if user and getattr(user, "tenant_id", None):
        return user.tenant_id
    return x_tenant_id or "default_tenant"


def get_vector_repository(session: AsyncSession = Depends(get_db)) -> VectorMetadataRepository:
    """Inject a `VectorMetadataRepository` bound to the current request transaction session."""
    return VectorMetadataRepository(session)


def get_vector_service(session: AsyncSession = Depends(get_db)) -> VectorStorageService:
    """Inject a `VectorStorageService` configured with global event dispatcher and Qdrant provider."""
    return VectorStorageService(session=session, dispatcher=get_dispatcher())
