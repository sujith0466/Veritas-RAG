"""Authentication Service.

Encapsulates JWT token validation and non-destructive, idempotent
user synchronization between Supabase identities and PostgreSQL.
"""

from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.core.auth.context import UserContext
from backend.core.exceptions.auth import AuthenticationException
from backend.core.permissions.rbac import Role
from backend.core.security.audit import log_auth_event
from backend.core.security.jwt import get_jwt_verifier
from backend.repositories.implementations.user_repository import UserRepository

logger = structlog.get_logger(__name__)


class AuthService:
    """Orchestrates authentication, token decoding, and non-destructive user sync."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.user_repo = UserRepository(session)
        self.jwt_verifier = get_jwt_verifier()

    async def authenticate_token(self, token: str) -> UserContext:
        """Verify JWT and synchronize the user identity non-destructively.

        Args:
            token: Raw Bearer JWT token string.

        Returns:
            A populated UserContext for the authenticated request.

        Raises:
            AuthenticationException: If the account is disabled or missing credentials.
            InvalidTokenException: If token signature or claims are invalid.
            ExpiredTokenException: If token has expired.
        """
        payload = self.jwt_verifier.verify_and_decode(token)

        # Lookup user by Supabase UUID
        user = await self.user_repo.get_by_supabase_id(payload.sub)

        if user:
            # Non-destructive sync: update ONLY Supabase-owned identity fields if changed.
            # Application-owned fields (role, is_active, tenant_id) are preserved.
            if payload.email and user.email != payload.email:
                logger.info(
                    "Syncing updated Supabase email for existing user",
                    user_id=str(user.id),
                    old_email=user.email,
                    new_email=payload.email,
                )
                user = await self.user_repo.update(user, email=payload.email)
        else:
            # First-time login: create new user with default role
            email = payload.email or f"{payload.sub}@supabase.local"
            initial_role = Role.from_str(payload.role)
            logger.info(
                "Creating new user during idempotent sync",
                supabase_id=payload.sub,
                email=email,
                role=initial_role.value,
            )
            user = await self.user_repo.create(
                supabase_user_id=payload.sub,
                email=email,
                role=initial_role.value,
                is_active=True,
            )

        if not user.is_active:
            await log_auth_event(
                session=self.session,
                action="user.authenticate.disabled",
                resource_type="auth",
                user_id=user.id,
                metadata={"supabase_id": payload.sub},
            )
            raise AuthenticationException("User account is disabled")

        await log_auth_event(
            session=self.session,
            action="user.authenticate",
            resource_type="auth",
            user_id=user.id,
            metadata={"supabase_id": payload.sub, "role": user.role},
        )

        return UserContext(
            id=user.id,
            supabase_id=str(user.supabase_user_id),
            email=user.email,
            role=Role.from_str(user.role),
            is_active=user.is_active,
            tenant_id=None,
        )
