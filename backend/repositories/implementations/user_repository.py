"""User Repository Implementation.

Provides concrete SQLAlchemy queries for User entity management.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.entities.user import User
from backend.repositories.base import BaseRepository
from backend.repositories.interfaces.user_repository import IUserRepository


class UserRepository(BaseRepository[User], IUserRepository):
    """SQLAlchemy implementation of the User repository."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, User)

    async def get_by_email(self, email: str) -> User | None:
        """Fetch an active user by their email address."""
        stmt = select(User).where(
            User.email == email,
            User.is_deleted.is_(False),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def exists_by_email(self, email: str) -> bool:
        """Check if an active user exists with the given email."""
        stmt = select(User.id).where(
            User.email == email,
            User.is_deleted.is_(False),
        )
        result = await self.session.execute(stmt)
        return result.first() is not None

    async def get_by_username(self, username: str) -> User | None:
        """Fetch an active user by their username."""
        stmt = select(User).where(
            User.username == username,
            User.is_deleted.is_(False),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def exists_by_username(self, username: str) -> bool:
        """Check if an active user exists with the given username."""
        stmt = select(User.id).where(
            User.username == username,
            User.is_deleted.is_(False),
        )
        result = await self.session.execute(stmt)
        return result.first() is not None
