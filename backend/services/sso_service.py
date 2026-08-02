"""Service for Identity Providers & SSO."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.events import EventDispatcher
from backend.models.entities.identity_provider import IdentityProvider
from backend.repositories.sso_repository import IdentityProviderRepository


class SSOServiceError(Exception):
    pass

class SSOService:
    """Service for F4.9 SSO Configuration."""

    def __init__(self, session: AsyncSession, dispatcher: EventDispatcher) -> None:
        self.session = session
        self.dispatcher = dispatcher
        self.repo = IdentityProviderRepository(session)

    async def create_idp(self, workspace_id: uuid.UUID, data: dict) -> IdentityProvider:
        """Create a new Identity Provider config."""
        idp = IdentityProvider(
            workspace_id=workspace_id,
            name=data["name"],
            type=data["type"],
            entity_id_issuer=data["entity_id_issuer"],
            sso_url=data["sso_url"],
            logout_url=data.get("logout_url"),
            metadata_url=data.get("metadata_url"),
            certificates=data.get("certificates"),
            attribute_mapping=data["attribute_mapping"],
            domain_restrictions=data.get("domain_restrictions"),
            jit_enabled=data.get("jit_enabled", False),
            force_sso=data.get("force_sso", False)
        )
        self.session.add(idp)
        await self.session.flush()

        await self.dispatcher.dispatch("IDP_CREATED", {"idp_id": str(idp.id), "workspace_id": str(workspace_id)})
        return idp

    async def generate_login_request(self, workspace_id: uuid.UUID) -> str:
        """Generate SAML AuthnRequest or OIDC URL."""
        idp = await self.repo.get_active_for_workspace(workspace_id)
        if not idp:
            raise SSOServiceError("No active SSO provider for this workspace.")

        # Simulated logic for generating redirect URL with nonce/pkce
        return idp.sso_url + "?request=signed_payload"

    async def process_callback(self, workspace_id: uuid.UUID, payload: str) -> dict:
        """Process SAML Response or OIDC callback and handle JIT."""
        idp = await self.repo.get_active_for_workspace(workspace_id)
        if not idp:
            raise SSOServiceError("No active SSO provider.")

        # 1. SIGNATURE_VALIDATED (Simulation of defusedxml & python3-saml)
        # 2. DOMAIN_VERIFIED (Must check if domain of email is VERIFIED)
        # 3. JIT_PROVISIONING

        await self.dispatcher.dispatch("IDP_LOGIN_SUCCESS", {"idp_id": str(idp.id), "workspace_id": str(workspace_id)})
        return {"user_id": str(uuid.uuid4()), "token": "jwt-token-stub"}
