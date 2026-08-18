"""Idempotent seed script for development demo user."""

import os
import structlog

from backend.core.config import get_settings

logger = structlog.get_logger(__name__)


async def seed_demo_user() -> None:
    """Creates a demo user locally if running in development or ENABLE_DEMO_USER=true.

    The demo user is created idempotently (skips if exists).
    Role defaults to 'viewer' unless ENABLE_DEMO_ADMIN=true is set.
    """
    settings = get_settings()

    enable_demo = os.environ.get("ENABLE_DEMO_USER", "").lower() == "true"
    if not settings.app.is_development and not enable_demo:
        logger.debug(
            "Skipping demo user seed: not in development and ENABLE_DEMO_USER not set"
        )
        return

    demo_email = "demo@gmail.com"
    demo_password = "ChangeMe123!"
    demo_role = (
        "admin"
        if os.environ.get("ENABLE_DEMO_ADMIN", "").lower() == "true"
        else "viewer"
    )

    try:
        from backend.database.engine import get_session_factory
        from backend.core.security.password import get_password_hash
        from backend.models.entities.user import User
        from backend.core.permissions.rbac import Role
        from backend.repositories.implementations.user_repository import UserRepository

        async with get_session_factory()() as session:
            repo = UserRepository(session)

            # Users to seed
            users_to_seed = [
                ("demoadmin@gmail.com", "ChangeMe123!", "admin"),
                ("demo@gmail.com", "ChangeMe123!", "viewer")
            ]

            for email, password, role in users_to_seed:
                if await repo.exists_by_email(email):
                    logger.info("Demo user already exists locally. Skipping seed.", email=email)
                    continue

                hashed_pw = get_password_hash(password)
                await repo.create(
                    email=email,
                    hashed_password=hashed_pw,
                    role=Role.from_str(role),
                    is_verified=True,
                )
                logger.info("Demo user created successfully.", email=email, role=role)

            await session.commit()
    except Exception as e:
        logger.error("Exception occurred while seeding demo user", error=str(e))
