"""Audit Log Repository Interface.

Defines the contract for audit log trail persistence and querying.
"""

import uuid
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any

from backend.models.entities.audit_log import AuditLog


class IAuditLogRepository(ABC):
    """Abstract interface for audit log repository operations."""

    @abstractmethod
    async def get_by_id(self, entity_id: uuid.UUID) -> AuditLog | None:
        """Fetch an audit log entry by primary key ID."""
        ...

    @abstractmethod
    async def get_all(self, skip: int = 0, limit: int = 100) -> Sequence[AuditLog]:
        """Fetch all audit log entries with pagination."""
        ...

    @abstractmethod
    async def create(self, **kwargs: Any) -> AuditLog:
        """Create a new audit log record."""
        ...

    @abstractmethod
    async def get_by_action(
        self, action: str, skip: int = 0, limit: int = 100
    ) -> Sequence[AuditLog]:
        """Fetch audit logs filtered by action type."""
        ...

    @abstractmethod
    async def get_by_user_id(
        self, user_id: uuid.UUID, skip: int = 0, limit: int = 100
    ) -> Sequence[AuditLog]:
        """Fetch audit logs associated with a specific user."""
        ...
