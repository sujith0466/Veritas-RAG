"""User Repository Interface.

Defines the contract for user account persistence and lookups.
"""

import uuid
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any

from backend.models.entities.user import User


class IUserRepository(ABC):
    """Abstract interface for user repository operations."""

    @abstractmethod
    async def get_by_id(self, entity_id: uuid.UUID) -> User | None:
        """Fetch a user by primary key ID."""
        ...

    @abstractmethod
    async def get_all(self, skip: int = 0, limit: int = 100) -> Sequence[User]:
        """Fetch all active users with pagination."""
        ...

    @abstractmethod
    async def create(self, **kwargs: Any) -> User:
        """Create a new user record."""
        ...

    @abstractmethod
    async def update(self, instance: User, **kwargs: Any) -> User:
        """Update an existing user record."""
        ...

    @abstractmethod
    async def soft_delete(self, instance: User) -> None:
        """Soft-delete a user."""
        ...

    @abstractmethod
    async def get_by_email(self, email: str) -> User | None:
        """Fetch an active user by their email address."""
        ...

    @abstractmethod
    async def get_by_supabase_id(self, supabase_user_id: str) -> User | None:
        """Fetch an active user by their Supabase Auth ID."""
        ...
