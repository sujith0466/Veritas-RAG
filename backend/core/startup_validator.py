from __future__ import annotations

import sys

from sqlalchemy import text
import structlog

from backend.core.config import get_settings

logger = structlog.get_logger(__name__)

class StartupValidator:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def validate(self) -> None:
        """Run all startup validations. Abort application on failure."""
        logger.info("Starting configuration and dependency validation phase")

        try:
            self.validate_configuration()

            # Skip infrastructure network validation if explicitly disabled via configuration
            if self.settings.startup.validate_infrastructure:
                await self.validate_infrastructure()
            else:
                logger.info("Skipping infrastructure validation per configuration flag")

            logger.info("All startup validations passed successfully")
        except Exception as e:
            logger.critical("STARTUP VALIDATION FAILED", error=str(e))
            sys.exit(1)

    def validate_configuration(self) -> None:
        """Layer 1: Configuration validation. No network I/O."""
        self._validate_environment()
        self._validate_embeddings()
        self._validate_consistency()

    async def validate_infrastructure(self) -> None:
        """Layer 2: Infrastructure validation. Performs network I/O."""
        await self._validate_database()
        await self._validate_redis()
        await self._validate_qdrant()

    def _validate_environment(self) -> None:
        """Verify environment variables and configuration objects."""
        # Pydantic BaseSettings already enforces most requirements at instantiation.
        # We verify that standard critical config objects exist.
        if not self.settings.database.url:
            self._fail("Missing database.url configuration")
        if not self.settings.qdrant.host:
            self._fail("Missing qdrant.host configuration")
        if not self.settings.embeddings.default_provider:
            self._fail("Missing embeddings.default_provider configuration")

        self._pass("Environment Configuration")

    async def _validate_database(self) -> None:
        """Verify database connectivity and basic execution."""
        from backend.database.engine import get_session_factory
        session_maker = get_session_factory()
        try:
            async with session_maker() as session:
                await session.execute(text("SELECT 1"))
            self._pass("Database connection established")
        except Exception as e:
            self._fail(f"Database unavailable: {e}")

    async def _validate_redis(self) -> None:
        """Verify Redis connectivity if enabled in deployment."""
        if not self.settings.redis.url:
            return  # Not configured/required

        from backend.cache.client import get_redis_client
        try:
            redis = get_redis_client()
            await redis.ping()
            self._pass("Redis connection established")
        except Exception as e:
            self._fail(f"Redis unavailable: {e}")

    async def _validate_qdrant(self) -> None:
        """Verify Qdrant is reachable without mutating data."""
        from backend.vector_db.client import get_qdrant_client
        try:
            client = get_qdrant_client()
            # Just verify we can fetch collections (read-only)
            await client.get_collections()
            self._pass("Qdrant reachable and authenticated")
        except Exception as e:
            self._fail(f"Qdrant unavailable or authentication failed: {e}")

    def _validate_embeddings(self) -> None:
        """Verify embedding configuration."""
        if not self.settings.embeddings.openai_model:
            self._fail("Missing embeddings.openai_model configuration")

        self._pass(f"Embedding configuration validated (model={self.settings.embeddings.openai_model})")

    def _validate_consistency(self) -> None:
        """Verify internal configuration contracts."""
        # Confirm collection naming function exists and operates
        try:
            test_name = self.settings.qdrant.collection_name("test_tenant")
            if not test_name:
                self._fail("QdrantSettings.collection_name returned empty string")
        except Exception as e:
            self._fail(f"Collection naming function is missing or invalid: {e}")

        self._pass("Configuration contracts and consistency validated")

    def _pass(self, message: str) -> None:
        logger.info(f"[PASS] {message}")

    def _fail(self, message: str) -> None:
        logger.error(f"[FAIL] {message}")
        raise ValueError(message)

async def run_startup_validation() -> None:
    validator = StartupValidator()
    await validator.validate()
