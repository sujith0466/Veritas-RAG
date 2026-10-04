import re
import secrets
from typing import TYPE_CHECKING

from backend.api.v1.schemas.workspace_onboarding import (
    CROCKFORD_ALPHABET,
    WORKSPACE_ID_PATTERN,
    WORKSPACE_SLUG_PATTERN,
)

if TYPE_CHECKING:
    from backend.repositories.workspace import WorkspaceRepository


class WorkspaceIdGenerator:
    """Generates user-facing, stable, unique public Workspace IDs.

    Canonical format: ^[A-Z0-9]{2,20}(?:-[A-Z0-9]{2,12})*$
    Example: 'ACME-7X92KP', 'WS-8K2M9P'
    """

    DEFAULT_PREFIX = "WS"
    SUFFIX_LENGTH = 6
    MAX_ATTEMPTS = 15

    @classmethod
    def generate_candidate(cls, name: str | None = None) -> str:
        """Generates a candidate public Workspace ID from a workspace name and entropy."""
        prefix = cls.DEFAULT_PREFIX
        if name:
            clean = re.sub(r"[^A-Za-z0-9]+", "", name).upper()
            if len(clean) >= 2:
                prefix = clean[:10]

        suffix = "".join(secrets.choice(CROCKFORD_ALPHABET) for _ in range(cls.SUFFIX_LENGTH))
        candidate = f"{prefix}-{suffix}"

        if not re.match(WORKSPACE_ID_PATTERN, candidate):
            # Fallback to guaranteed format if unusual edge cases arise
            candidate = f"WS-{suffix}"

        return candidate

    @classmethod
    async def generate_unique_public_id(
        cls,
        workspace_repo: "WorkspaceRepository",
        name: str | None = None,
        max_attempts: int = MAX_ATTEMPTS,
    ) -> str:
        """Generates a unique public Workspace ID, resolving collisions via repository check."""
        for _ in range(max_attempts):
            candidate = cls.generate_candidate(name)
            if not await workspace_repo.exists_by_public_id(candidate):
                return candidate

        # If name-derived prefix suffered high collisions, switch to high-entropy fallback
        for _ in range(max_attempts):
            entropy_suffix = "".join(secrets.choice(CROCKFORD_ALPHABET) for _ in range(8))
            fallback_candidate = f"WS-{entropy_suffix}"
            if not await workspace_repo.exists_by_public_id(fallback_candidate):
                return fallback_candidate

        raise RuntimeError("Failed to generate a unique public Workspace ID after maximum attempts.")


class SlugGenerator:
    """Generates URL-safe workspace slugs with collision resolution.

    Canonical format: ^[a-z0-9]+(?:-[a-z0-9]+)*$
    Example: 'acme-corp', 'marketing-team-3f1a'
    """

    DEFAULT_BASE = "workspace"
    MAX_ATTEMPTS = 15

    @classmethod
    def generate_candidate(cls, name: str | None = None) -> str:
        """Generates a base lowercase URL-safe slug candidate."""
        if not name:
            return cls.DEFAULT_BASE

        base_slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        return base_slug if base_slug else cls.DEFAULT_BASE

    @classmethod
    async def generate_unique_slug(
        cls,
        workspace_repo: "WorkspaceRepository",
        name: str | None = None,
        max_attempts: int = MAX_ATTEMPTS,
    ) -> str:
        """Generates a unique slug, appending short hex suffixes if collision occurs."""
        base_slug = cls.generate_candidate(name)
        if not await workspace_repo.exists_by_slug(base_slug):
            return base_slug

        for _ in range(max_attempts):
            suffix = secrets.token_hex(2)
            candidate = f"{base_slug}-{suffix}"
            if re.match(WORKSPACE_SLUG_PATTERN, candidate) and not await workspace_repo.exists_by_slug(candidate):
                return candidate

        # Longer suffix fallback
        for _ in range(max_attempts):
            suffix = secrets.token_hex(4)
            candidate = f"{base_slug}-{suffix}"
            if not await workspace_repo.exists_by_slug(candidate):
                return candidate

        raise RuntimeError("Failed to generate a unique workspace slug after maximum attempts.")
