"""Authentication Service.

Encapsulates JWT token validation and non-destructive, idempotent
user synchronization between Supabase identities and PostgreSQL.
"""

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

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
            updates = {}
            if payload.email and user.email != payload.email:
                updates["email"] = payload.email

            # Idempotently sync missing or changed metadata
            current_profile = dict(user.profile_data or {})
            if payload.full_name and current_profile.get("full_name") != payload.full_name:
                current_profile["full_name"] = payload.full_name
                updates["profile_data"] = current_profile

            current_ws = dict(user.workspace_settings or {})
            if payload.organization_name and current_ws.get("organization_name") != payload.organization_name:
                current_ws["organization_name"] = payload.organization_name
                updates["workspace_settings"] = current_ws

            if updates:
                logger.info("Syncing updated metadata for existing user", user_id=str(user.id), updates=list(updates.keys()))
                user = await self.user_repo.update(user, **updates)
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
                tenant_id=payload.tenant_id,
                workspace_name=payload.workspace_name,
                profile_data={"full_name": payload.full_name} if payload.full_name else {},
                workspace_settings={"organization_name": payload.organization_name} if payload.organization_name else {},
            )

            # DEMO MODE Auto-seeding
            import os
            import asyncio
            if os.environ.get("DEMO_MODE", "").lower() == "true" and email == "demoadmin@gmail.com":
                try:
                    from backend.core.demo_seeder import run_seed_for_tenant
                    logger.info("Triggering automatic demo data seeding")
                    asyncio.create_task(run_seed_for_tenant(user.tenant_id, user.id))
                except Exception as e:
                    logger.error("Failed to start demo seeder", error=str(e))

        if not user.is_active:
            await log_auth_event(
                session=self.session,
                action="user.authenticate.disabled",
                resource_type="auth",
                user_id=user.id,
                metadata={"supabase_id": payload.sub},
            )
            await self.session.commit()
            raise AuthenticationException("User account is disabled")

        await log_auth_event(
            session=self.session,
            action="user.authenticate",
            resource_type="auth",
            user_id=user.id,
            metadata={"supabase_id": payload.sub, "role": user.role},
        )

        await self.session.commit()

        return UserContext(
            id=user.id,
            supabase_id=str(user.supabase_user_id),
            email=user.email,
            role=Role.from_str(user.role),
            is_active=user.is_active,
            tenant_id=user.tenant_id,
            workspace_name=user.workspace_name,
        )
