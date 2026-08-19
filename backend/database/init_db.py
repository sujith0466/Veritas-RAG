"""Database Initialization Utilities.

Handles startup health verification and testing table setup.
In production environments, schema migrations must be applied strictly via Alembic.
"""

import structlog

from backend.core.config import get_settings
from backend.database.base import Base
from backend.database.engine import get_engine

logger = structlog.get_logger(__name__)


async def init_db() -> None:
    """Verify database connectivity and initialize schema for testing if applicable.

    In production or staging, table creation is managed via Alembic migrations.
    When running in testing mode (`settings.is_testing`), tables can be created in-memory
    or on the test database directly.
    """
    settings = get_settings()
    engine = get_engine()

    logger.info("Verifying database connectivity during init_db")
    if settings.is_testing:
        logger.info("Testing environment detected; creating database schema directly")
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        except Exception as exc:
            logger.warning(
                "Could not connect to test database during init_db", error=str(exc)
            )
    else:
        # Verify connection by executing a quick check
        try:
            from sqlalchemy import text
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
                logger.info("Database connection established successfully")
        except Exception as exc:
            logger.warning("Database connection failed during init_db", error=str(exc))
