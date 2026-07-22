"""Idempotent seed script for development demo user."""

import os

import httpx
import structlog

from backend.core.config import get_settings

logger = structlog.get_logger(__name__)


async def seed_demo_user() -> None:
    """Creates a demo user in Supabase if running in development or ENABLE_DEMO_USER=true.

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

    supabase_url = settings.supabase.url.rstrip("/")
    admin_api_url = f"{supabase_url}/auth/v1/admin/users"
    headers = {
        "apikey": settings.supabase.service_role_key,
        "Authorization": f"Bearer {settings.supabase.service_role_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient() as client:
            # Check if user already exists
            resp = await client.get(admin_api_url, headers=headers)
            if resp.status_code == 200:
                users = resp.json().get("users", [])
                if any(u.get("email") == demo_email for u in users):
                    logger.info(
                        "Demo user already exists in Supabase. Skipping seed.",
                        email=demo_email,
                    )
                    return

            # Create user
            payload = {
                "email": demo_email,
                "password": demo_password,
                "email_confirm": True,
                "user_metadata": {"role": demo_role},
            }
            logger.info(
                "Creating demo user in Supabase", email=demo_email, role=demo_role
            )
            create_resp = await client.post(
                admin_api_url, headers=headers, json=payload
            )

            if create_resp.status_code in (200, 201):
                logger.info("Demo user created successfully.")
            elif create_resp.status_code == 422:
                # E.g. "User already registered"
                logger.info("Demo user already exists (422). Skipping.")
            else:
                logger.error(
                    "Failed to create demo user",
                    status=create_resp.status_code,
                    response=create_resp.text,
                )
    except Exception as e:
        logger.error("Exception occurred while seeding demo user", error=str(e))
