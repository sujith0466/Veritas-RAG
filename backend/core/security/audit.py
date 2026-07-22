"""Audit logging infrastructure hooks for authentication and authorization events.

Provides non-blocking helpers to record security decisions into the audit_logs table.
"""

import uuid
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from backend.repositories.implementations.audit_log_repository import \
    AuditLogRepository

logger = structlog.get_logger(__name__)


async def log_auth_event(
    session: AsyncSession,
    action: str,
    resource_type: str,
    user_id: uuid.UUID | None = None,
    resource_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> None:
    """Record an authentication or authorization audit event.

    Args:
        session: Active async database session.
        action: Identifier of the event (e.g., 'user.authenticate', 'permission.denied').
        resource_type: Category of resource (e.g., 'auth', 'endpoint', 'role').
        user_id: Internal primary key of the acting user if known.
        resource_id: Optional identifier of the targeted resource.
        metadata: Optional structured context payload.
        ip_address: Client IP address if available from request headers.
    """
    try:
        repo = AuditLogRepository(session)
        await repo.create(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata=metadata or {},
            ip_address=ip_address,
        )
    except Exception as e:
        # Audit log failures must never crash the primary request path
        logger.error(
            "Failed to write audit log entry",
            action=action,
            user_id=str(user_id) if user_id else None,
            error=str(e),
        )
