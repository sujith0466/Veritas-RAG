import re
from unittest.mock import AsyncMock
import pytest

from backend.api.v1.schemas.workspace_onboarding import (
    CROCKFORD_ALPHABET,
    WORKSPACE_ID_PATTERN,
    WORKSPACE_SLUG_PATTERN,
)
from backend.services.workspace.identity import SlugGenerator, WorkspaceIdGenerator


class TestWorkspaceIdGenerator:
    def test_generate_candidate_default_prefix(self):
        candidate = WorkspaceIdGenerator.generate_candidate(None)
        assert candidate.startswith("WS-")
        assert len(candidate) == 9  # 'WS-' + 6 chars
        assert re.match(WORKSPACE_ID_PATTERN, candidate)

    def test_generate_candidate_name_sanitization(self):
        candidate = WorkspaceIdGenerator.generate_candidate("Acme Global Systems, Inc.")
        assert candidate.startswith("ACMEGLOBAL-")
        assert re.match(WORKSPACE_ID_PATTERN, candidate)

    def test_generate_candidate_short_name_fallback(self):
        candidate = WorkspaceIdGenerator.generate_candidate("A!")
        assert candidate.startswith("WS-")
        assert re.match(WORKSPACE_ID_PATTERN, candidate)

    def test_generate_candidate_crockford_characters_only(self):
        candidate = WorkspaceIdGenerator.generate_candidate("Test")
        prefix, suffix = candidate.split("-", 1)
        assert prefix == "TEST"
        assert len(suffix) == 6
        for char in suffix:
            assert char in CROCKFORD_ALPHABET
            assert char not in {"0", "O", "1", "I", "L"}

    @pytest.mark.asyncio
    async def test_generate_unique_public_id_no_collision(self):
        repo = AsyncMock()
        repo.exists_by_public_id.return_value = False

        pub_id = await WorkspaceIdGenerator.generate_unique_public_id(repo, "Engineering")
        assert pub_id.startswith("ENGINEERIN-")
        assert repo.exists_by_public_id.await_count == 1
        assert re.match(WORKSPACE_ID_PATTERN, pub_id)

    @pytest.mark.asyncio
    async def test_generate_unique_public_id_with_collision_retry(self):
        repo = AsyncMock()
        # First two collision, third succeeds
        repo.exists_by_public_id.side_effect = [True, True, False]

        pub_id = await WorkspaceIdGenerator.generate_unique_public_id(repo, "Analytics")
        assert pub_id.startswith("ANALYTICS-")
        assert repo.exists_by_public_id.await_count == 3
        assert re.match(WORKSPACE_ID_PATTERN, pub_id)

    @pytest.mark.asyncio
    async def test_generate_unique_public_id_fallback_after_max_attempts(self):
        repo = AsyncMock()
        # Collide for MAX_ATTEMPTS (15), then succeed on fallback
        side_effects = [True] * 15 + [False]
        repo.exists_by_public_id.side_effect = side_effects

        pub_id = await WorkspaceIdGenerator.generate_unique_public_id(repo, "PopularName")
        assert pub_id.startswith("WS-")
        assert repo.exists_by_public_id.await_count == 16
        assert re.match(WORKSPACE_ID_PATTERN, pub_id)


class TestSlugGenerator:
    def test_generate_candidate_slug(self):
        slug = SlugGenerator.generate_candidate("Acme Enterprise AI")
        assert slug == "acme-enterprise-ai"
        assert re.match(WORKSPACE_SLUG_PATTERN, slug)

    def test_generate_candidate_empty_fallback(self):
        slug = SlugGenerator.generate_candidate("   !@#$$%  ")
        assert slug == "workspace"

    @pytest.mark.asyncio
    async def test_generate_unique_slug_no_collision(self):
        repo = AsyncMock()
        repo.exists_by_slug.return_value = False

        slug = await SlugGenerator.generate_unique_slug(repo, "Dev Team")
        assert slug == "dev-team"
        assert repo.exists_by_slug.await_count == 1

    @pytest.mark.asyncio
    async def test_generate_unique_slug_with_collision(self):
        repo = AsyncMock()
        repo.exists_by_slug.side_effect = [True, False]

        slug = await SlugGenerator.generate_unique_slug(repo, "Dev Team")
        assert slug.startswith("dev-team-")
        assert repo.exists_by_slug.await_count == 2
        assert re.match(WORKSPACE_SLUG_PATTERN, slug)


class TestIdentifierIndependence:
    def test_public_id_and_slug_are_independent(self):
        name = "Alpha Beta Gamma"
        slug = SlugGenerator.generate_candidate(name)
        public_id = WorkspaceIdGenerator.generate_candidate(name)

        assert slug == "alpha-beta-gamma"
        assert public_id.startswith("ALPHABETAG-")
        # Ensure distinct casing, format, and structure
        assert slug != public_id
        assert slug.islower()
        assert public_id.isupper()
