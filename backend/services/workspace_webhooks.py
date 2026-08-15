import ipaddress
import secrets
import socket
from urllib.parse import urlparse
import uuid
import hashlib

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.entities.workspace_webhook import WorkspaceWebhook
from backend.api.v1.schemas.workspace_webhook import WorkspaceWebhookCreateDTO, WorkspaceWebhookUpdateDTO

class WebhookValidationException(Exception):
    pass

class WebhookNotFoundException(Exception):
    pass

class WorkspaceWebhookService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _resolve_and_validate_url(self, url: str) -> None:
        """
        Validates URL strictly to prevent SSRF at configuration time.
        Must use HTTPS, and resolve to a public IP address.
        """
        parsed = urlparse(url)
        if parsed.scheme != "https":
            raise WebhookValidationException("Webhook URL must use HTTPS.")
        
        hostname = parsed.hostname
        if not hostname:
            raise WebhookValidationException("Invalid hostname in URL.")
            
        try:
            # Resolve all IPs for the hostname
            addr_info = socket.getaddrinfo(hostname, 443, socket.AF_INET, socket.SOCK_STREAM)
        except socket.gaierror:
            raise WebhookValidationException(f"Could not resolve hostname: {hostname}")

        for info in addr_info:
            ip_str = info[4][0]
            try:
                ip_obj = ipaddress.ip_address(ip_str)
            except ValueError:
                continue
            
            # Block specific cloud metadata IPs manually just in case
            if str(ip_obj) == "169.254.169.254":
                raise WebhookValidationException("Cloud metadata endpoint access is strictly prohibited.")

            # Explicitly block non-global IPs
            if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_multicast:
                raise WebhookValidationException(f"Resolved IP {ip_str} is in a protected or private range.")

    async def create_webhook(self, tenant_id: uuid.UUID, data: WorkspaceWebhookCreateDTO) -> tuple[WorkspaceWebhook, str]:
        """Creates a webhook and returns (Webhook, plaintext_secret)."""
        url_str = str(data.endpoint_url)
        await self._resolve_and_validate_url(url_str)
        
        raw_secret = secrets.token_urlsafe(32)
        # In a real system, this should be symmetrically encrypted via KMS.
        # Storing plaintext here so the delivery worker can sign payloads.
        secret_hash = raw_secret

        webhook = WorkspaceWebhook(
            tenant_id=tenant_id,
            endpoint_url=url_str,
            secret_hash=secret_hash,
            events=data.events,
            is_active=data.is_active
        )
        self.session.add(webhook)
        await self.session.commit()
        await self.session.refresh(webhook)
        
        return webhook, raw_secret

    async def get_webhooks(self, tenant_id: uuid.UUID) -> list[WorkspaceWebhook]:
        stmt = select(WorkspaceWebhook).where(
            WorkspaceWebhook.tenant_id == tenant_id,
            WorkspaceWebhook.is_deleted == False
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_webhook(self, tenant_id: uuid.UUID, webhook_id: uuid.UUID, data: WorkspaceWebhookUpdateDTO) -> WorkspaceWebhook:
        stmt = select(WorkspaceWebhook).where(
            WorkspaceWebhook.tenant_id == tenant_id,
            WorkspaceWebhook.id == webhook_id,
            WorkspaceWebhook.is_deleted == False
        )
        result = await self.session.execute(stmt)
        webhook = result.scalars().first()
        if not webhook:
            raise WebhookNotFoundException("Webhook not found.")
            
        if data.endpoint_url is not None:
            url_str = str(data.endpoint_url)
            await self._resolve_and_validate_url(url_str)
            webhook.endpoint_url = url_str
            
        if data.events is not None:
            webhook.events = data.events
            
        if data.is_active is not None:
            webhook.is_active = data.is_active
            
        await self.session.commit()
        await self.session.refresh(webhook)
        return webhook

    async def delete_webhook(self, tenant_id: uuid.UUID, webhook_id: uuid.UUID) -> None:
        stmt = select(WorkspaceWebhook).where(
            WorkspaceWebhook.tenant_id == tenant_id,
            WorkspaceWebhook.id == webhook_id,
            WorkspaceWebhook.is_deleted == False
        )
        result = await self.session.execute(stmt)
        webhook = result.scalars().first()
        if not webhook:
            raise WebhookNotFoundException("Webhook not found.")
            
        webhook.is_deleted = True
        await self.session.commit()
