"""Permission guard checks and abstractions.

Provides reusable evaluation helpers for role and permission authorization.
"""

import re
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from .rbac import Role
from .registry import Permission, get_permission_registry

logger = structlog.get_logger(__name__)

DIAGNOSTIC_TICKET_PATTERN = re.compile(r"^[A-Z0-9_-]{3,64}$")


def validate_diagnostic_ticket(ticket_id: str | None) -> str:
    """Validate justification ticket ID format server-side (WP-7 / DEC-11).

    Enforces format ^[A-Z0-9_-]{3,64}$. Missing, empty, whitespace-only,
    or non-matching ticket IDs raise HTTP 400 Bad Request.
    """
    if not ticket_id or not isinstance(ticket_id, str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required diagnostic ticket header 'X-Justification-Ticket-ID'.",
        )
    cleaned = ticket_id.strip()
    if not DIAGNOSTIC_TICKET_PATTERN.match(cleaned):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed justification ticket ID. Must match ^[A-Z0-9_-]{3,64}$.",
        )
    return cleaned


async def record_diagnostic_access(
    session: AsyncSession | None = None,
    user_id: uuid.UUID | None = None,
    user_role: str = "",
    action: str = "",
    resource_type: str = "",
    resource_id: str = "",
    ticket_id: str = "",
    tenant_id: uuid.UUID | None = None,
    *,
    session_factory: Any | None = None,
) -> None:
    """Persist an append-only diagnostic audit log entry (WP-7 / DEC-11 / WP-7.1).

    WP-7.1 Autonomous Persistence Contract:
    To guarantee durable audit persistence without risking accidental commits of
    unrelated dirty/pending objects on the caller's request session, this function
    durably commits the audit record using an autonomous session (isolated transaction).

    If an explicit `session_factory` is provided, an autonomous session is created from it.
    Otherwise, the session factory is obtained from `get_session_factory()`.

    Fails closed: Any database failure during audit log insertion or commit
    aborts the request with HTTP 500 Internal Server Error, ensuring zero
    unaudited diagnostic access.
    """
    try:
        from backend.models.entities.audit_log import AuditLog

        audit_entry = AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details={
                "justification_ticket_id": ticket_id,
                "caller_role": user_role,
                "diagnostic_action": action,
                "timestamp": datetime.now(UTC).isoformat(),
            },
            status="success",
        )

        factory = session_factory
        if factory is None:
            from backend.database.engine import get_session_factory

            factory = get_session_factory()

        async with factory() as auto_session:
            auto_session.add(audit_entry)
            await auto_session.commit()
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "diagnostic_access_audit_failed",
            error=str(exc),
            user_id=str(user_id),
            action=action,
            ticket_id=ticket_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Diagnostic access audit persistence failed: request aborted.",
        ) from exc


ROLE_HIERARCHY: dict[Role, int] = {
    Role.PLATFORM_ADMIN: 100,
    Role.OWNER: 90,
    Role.ADMIN: 80,
    Role.ENGINEER: 70,
    Role.ANALYST: 60,
    Role.MEMBER: 50,
    Role.VIEWER: 10,
    Role.PLATFORM_SUPPORT: 5,
    Role.PLATFORM_AUDITOR: 5,
}


def evaluate_role_access(
    user_role: Role | str,
    allowed_roles: tuple[Role | str, ...],
    is_suspended: bool = False,
) -> bool:
    """Evaluate whether user_role is authorized among allowed_roles according to role hierarchy."""
    if is_suspended:
        return False

    if isinstance(user_role, str):
        user_role = Role.from_str(user_role)

    parsed_allowed = [
        Role.from_str(r) if isinstance(r, str) else r for r in allowed_roles
    ]

    # Platform Admin exclusive isolation: if only PLATFORM_ADMIN is allowed, only PLATFORM_ADMIN can enter
    if Role.PLATFORM_ADMIN in parsed_allowed and len(parsed_allowed) == 1:
        return user_role == Role.PLATFORM_ADMIN

    # PLATFORM_ADMIN has super-authority across all standard routes
    if user_role == Role.PLATFORM_ADMIN:
        return True

    # Owner exclusive isolation: if only OWNER is allowed, ADMIN cannot enter
    if Role.OWNER in parsed_allowed and len(parsed_allowed) == 1:
        return user_role == Role.OWNER

    # Admin and Owner possess authority over standard workspace routes
    if user_role in (Role.ADMIN, Role.OWNER):
        return True

    # Viewer routes are accessible to all active workspace roles
    if Role.VIEWER in parsed_allowed and user_role in (
        Role.MEMBER,
        Role.ENGINEER,
        Role.ANALYST,
        Role.VIEWER,
    ):
        return True

    return user_role in parsed_allowed


def evaluate_permission_access(
    user_role: Role | str,
    required_permission: Permission | str,
    is_suspended: bool = False,
) -> bool:
    """Evaluate whether user_role possesses required_permission using the registry."""
    registry = get_permission_registry()
    return registry.has_permission(
        user_role, required_permission, is_suspended=is_suspended
    )
