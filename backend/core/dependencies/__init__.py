"""FastAPI dependency injection generators (`backend/core/dependencies/`).

Provides request-scoped async generators yielding database sessions (`AsyncSession`),
Redis clients (`Redis`), Qdrant clients (`AsyncQdrantClient`), repositories, and
authentication/authorization dependencies.
"""

from __future__ import annotations

from .auth import (
    get_current_user,
    get_optional_user,
    require_authenticated,
    require_permission,
    require_role,
)
from .database import (
    get_audit_log_repository,
    get_cache,
    get_db,
    get_user_repository,
    get_vector_db,
)

__all__ = [
    "get_audit_log_repository",
    "get_cache",
    "get_current_user",
    "get_db",
    "get_optional_user",
    "get_user_repository",
    "get_vector_db",
    "require_authenticated",
    "require_permission",
    "require_role",
]
