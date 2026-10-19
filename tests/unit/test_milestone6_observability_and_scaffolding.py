"""Unit tests for Milestone 6: Observability, UX Performance & Scaffolding Scope (AUD-012, AUD-014, AUD-015)."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from backend.core.startup_validator import StartupValidator


# ==============================================================================
# AUD-012 Tests: Qdrant Startup Connectivity Verification
# ==============================================================================

@pytest.mark.asyncio
async def test_aud012_qdrant_startup_validation_success():
    """When Qdrant client get_collections() succeeds, validation passes cleanly."""
    validator = StartupValidator()

    mock_client = AsyncMock()
    mock_client.get_collections = AsyncMock(return_value=MagicMock(collections=[]))

    with patch("backend.vector_db.client.get_qdrant_client", return_value=mock_client):
        # Must execute without raising ValueError
        await validator._validate_qdrant()

    assert mock_client.get_collections.called


@pytest.mark.asyncio
async def test_aud012_qdrant_startup_validation_failure_raises():
    """When Qdrant is unreachable or down, _validate_qdrant() raises ValueError (failing startup)."""
    validator = StartupValidator()

    mock_client = AsyncMock()
    mock_client.get_collections = AsyncMock(side_effect=ConnectionError("Cannot connect to Qdrant on port 6333"))

    with patch("backend.vector_db.client.get_qdrant_client", return_value=mock_client):
        with pytest.raises(ValueError, match="Qdrant unavailable or authentication failed"):
            await validator._validate_qdrant()


@pytest.mark.asyncio
async def test_aud012_validate_infrastructure_invokes_qdrant():
    """validate_infrastructure() executes database, redis, and qdrant checks."""
    validator = StartupValidator()

    with patch.object(validator, "_validate_database", new_callable=AsyncMock) as mock_db, \
         patch.object(validator, "_validate_redis", new_callable=AsyncMock) as mock_redis, \
         patch.object(validator, "_validate_qdrant", new_callable=AsyncMock) as mock_qdrant:

        await validator.validate_infrastructure()

        assert mock_db.called
        assert mock_redis.called
        assert mock_qdrant.called


@pytest.mark.asyncio
async def test_aud012_startup_skips_infrastructure_when_disabled():
    """When settings.startup.validate_infrastructure is False, network validations are skipped."""
    validator = StartupValidator()
    validator.settings.startup.validate_infrastructure = False

    with patch.object(validator, "validate_configuration") as mock_conf, \
         patch.object(validator, "validate_infrastructure", new_callable=AsyncMock) as mock_infra:

        await validator.validate()

        assert mock_conf.called
        assert not mock_infra.called


# ==============================================================================
# AUD-015 Tests: API v2 Scaffolding Hygiene
# ==============================================================================

def test_aud015_api_v2_scaffolding_hygiene():
    """Verify backend/api/v2 contains documented architecture note and no untracked dead code."""
    v2_readme = Path("backend/api/v2/README.md")
    assert v2_readme.exists(), "backend/api/v2/README.md must exist to document scaffolding reservation"
    content = v2_readme.read_text(encoding="utf-8")
    assert "reserved for future" in content.lower()
