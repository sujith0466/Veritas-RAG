"""Domain Service for managing workspace verification."""

from datetime import UTC, datetime, timedelta
import hashlib
import secrets
import uuid

import idna
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.events import EventDispatcher
from backend.models.entities.workspace_domain import DomainCooldown, WorkspaceDomain
from backend.repositories.domain_repository import WorkspaceDomainRepository
from backend.tasks.dns_verification import trigger_dns_verification_task


class DomainServiceError(Exception):
    pass

class DomainCooldownError(DomainServiceError):
    pass

class DomainAlreadyVerifiedError(DomainServiceError):
    pass

class WorkspaceDomainService:
    """Service for F4.8 Domain Verification."""

    def __init__(self, session: AsyncSession, dispatcher: EventDispatcher) -> None:
        self.session = session
        self.dispatcher = dispatcher
        self.repo = WorkspaceDomainRepository(session)

    async def add_domain(self, workspace_id: uuid.UUID, raw_domain: str) -> tuple[WorkspaceDomain, str]:
        """Add a domain for verification."""
        try:
            # Normalize Punycode and lowercase
            normalized_domain = idna.encode(raw_domain.lower()).decode("utf-8")
        except idna.IDNAError as e:
            raise DomainServiceError("Invalid domain format") from e

        # Check global duplicate
        if await self.repo.is_verified_globally(normalized_domain):
            raise DomainAlreadyVerifiedError(f"Domain {normalized_domain} is already verified by another workspace.")

        # Check cooldown
        cooldown = await self.repo.get_cooldown(normalized_domain)
        if cooldown:
            raise DomainCooldownError(f"Domain is currently in a 24-hour cooldown until {cooldown.cooldown_expires_at}.")

        # Generate Token
        plaintext_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(plaintext_token.encode("utf-8")).hexdigest()

        domain = WorkspaceDomain(
            workspace_id=workspace_id,
            domain_name=normalized_domain,
            verification_token_hash=token_hash,
            status="PENDING",
            token_expires_at=datetime.now(UTC) + timedelta(days=7)
        )
        self.session.add(domain)
        await self.session.flush()

        await self.dispatcher.dispatch("DOMAIN_CREATED", {"domain_id": str(domain.id), "workspace_id": str(workspace_id)})

        return domain, plaintext_token

    async def trigger_verification(self, domain_id: uuid.UUID) -> None:
        """Trigger the background verification task."""
        domain = await self.repo.get_by_id(domain_id)
        if not domain:
            raise DomainServiceError("Domain not found")

        domain.status = "VERIFYING"
        await self.session.flush()

        trigger_dns_verification_task.delay(str(domain_id))

    async def remove_domain(self, workspace_id: uuid.UUID, domain_id: uuid.UUID) -> None:
        """Revoke and delete a domain, applying cooldown."""
        domain = await self.repo.get_by_id(domain_id)
        if not domain or domain.workspace_id != workspace_id:
            raise DomainServiceError("Domain not found")

        if domain.status == "VERIFIED":
            # Apply 24h cooldown
            cooldown = DomainCooldown(
                domain_name=domain.domain_name,
                released_by_workspace_id=workspace_id,
                cooldown_expires_at=datetime.now(UTC) + timedelta(hours=24)
            )
            await self.repo.add_cooldown(cooldown)

        domain.is_deleted = True
        await self.session.flush()

        await self.dispatcher.dispatch("DOMAIN_REVOKED", {"domain_name": domain.domain_name, "workspace_id": str(workspace_id)})
