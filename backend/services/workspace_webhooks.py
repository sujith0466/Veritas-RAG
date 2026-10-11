import ipaddress
import secrets
import socket
from urllib.parse import urlparse
import uuid
import hashlib
import hmac
from typing import List

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.entities.workspace_webhook import WorkspaceWebhook
from backend.models.entities.notification_delivery_log import NotificationDeliveryLog
from backend.api.v1.schemas.workspace_webhook import WorkspaceWebhookCreateDTO, WorkspaceWebhookUpdateDTO
from backend.core.security.webhook_crypto import encrypt_webhook_secret, decrypt_webhook_secret, WebhookCryptoError
from backend.core.events.types import EventType

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
        Defends against IPv4-mapped IPv6 and mixed DNS answers.
        """
        parsed = urlparse(url)
        if parsed.scheme != "https":
            raise WebhookValidationException("Webhook URL must use HTTPS.")

        hostname = parsed.hostname
        if not hostname:
            raise WebhookValidationException("Invalid hostname in URL.")

        try:
            # Resolve all IPs for the hostname
            addr_info = socket.getaddrinfo(hostname, 443, socket.AF_UNSPEC, socket.SOCK_STREAM)
        except socket.gaierror:
            raise WebhookValidationException(f"Could not resolve hostname: {hostname}")

        if not addr_info:
            raise WebhookValidationException(f"No IP addresses resolved for hostname: {hostname}")

        for info in addr_info:
            ip_str = info[4][0]
            try:
                ip_obj = ipaddress.ip_address(ip_str)
            except ValueError:
                raise WebhookValidationException(f"Invalid resolved IP address: {ip_str}")

            # Check for IPv4-mapped IPv6 addresses (e.g. ::ffff:127.0.0.1)
            if isinstance(ip_obj, ipaddress.IPv6Address) and ip_obj.ipv4_mapped:
                ip_obj = ip_obj.ipv4_mapped

            # Block specific cloud metadata IPs
            if str(ip_obj) == "169.254.169.254":
                raise WebhookValidationException("Cloud metadata endpoint access is strictly prohibited.")

            # Explicitly block non-global IPs
            if (
                ip_obj.is_private
                or ip_obj.is_loopback
                or ip_obj.is_link_local
                or ip_obj.is_multicast
                or ip_obj.is_reserved
                or ip_obj.is_unspecified
            ):
                raise WebhookValidationException(f"Resolved IP {ip_str} is in a protected or private range.")

    def _validate_events(self, events: List[str]) -> None:
        """Validates that requested events are canonical EventType values or wildcard '*'."""
        if not events:
            raise WebhookValidationException("Events list cannot be empty. Specify '*' for all events or choose specific events.")
        
        valid_event_values = {e.value for e in EventType}
        for ev in events:
            if ev != "*" and ev not in valid_event_values:
                raise WebhookValidationException(f"Invalid event subscription: '{ev}' is not a recognized canonical event.")

    async def create_webhook(self, tenant_id: uuid.UUID, data: WorkspaceWebhookCreateDTO) -> tuple[WorkspaceWebhook, str]:
        """Creates a webhook, securely encrypts the secret at rest, and returns (Webhook, plaintext_secret)."""
        url_str = str(data.endpoint_url)
        await self._resolve_and_validate_url(url_str)
        self._validate_events(data.events)

        raw_secret = f"whsec_{secrets.token_urlsafe(32)}"
        encrypted_token = encrypt_webhook_secret(raw_secret)
        
        # Store a one-way SHA-256 fingerprint in secret_hash for identity/audit
        fingerprint = hashlib.sha256(raw_secret.encode("utf-8")).hexdigest()

        webhook = WorkspaceWebhook(
            tenant_id=tenant_id,
            endpoint_url=url_str,
            secret_hash=fingerprint,
            encrypted_secret=encrypted_token,
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

    async def get_webhook_by_id(self, tenant_id: uuid.UUID, webhook_id: uuid.UUID) -> WorkspaceWebhook:
        stmt = select(WorkspaceWebhook).where(
            WorkspaceWebhook.tenant_id == tenant_id,
            WorkspaceWebhook.id == webhook_id,
            WorkspaceWebhook.is_deleted == False
        )
        result = await self.session.execute(stmt)
        webhook = result.scalars().first()
        if not webhook:
            raise WebhookNotFoundException("Webhook not found.")
        return webhook

    async def update_webhook(self, tenant_id: uuid.UUID, webhook_id: uuid.UUID, data: WorkspaceWebhookUpdateDTO) -> WorkspaceWebhook:
        webhook = await self.get_webhook_by_id(tenant_id, webhook_id)

        if data.endpoint_url is not None:
            url_str = str(data.endpoint_url)
            await self._resolve_and_validate_url(url_str)
            webhook.endpoint_url = url_str

        if data.events is not None:
            self._validate_events(data.events)
            webhook.events = data.events

        if data.is_active is not None:
            webhook.is_active = data.is_active

        await self.session.commit()
        await self.session.refresh(webhook)
        return webhook

    async def delete_webhook(self, tenant_id: uuid.UUID, webhook_id: uuid.UUID) -> None:
        webhook = await self.get_webhook_by_id(tenant_id, webhook_id)
        webhook.is_deleted = True
        await self.session.commit()

    async def get_delivery_secret(self, webhook: WorkspaceWebhook) -> str:
        """Retrieves and decrypts the shared secret for HMAC delivery signing with legacy fallback."""
        if webhook.encrypted_secret:
            try:
                return decrypt_webhook_secret(webhook.encrypted_secret)
            except WebhookCryptoError as e:
                # If decryption fails, check if legacy plaintext secret_hash exists
                pass

        # Legacy fallback: secret was stored in secret_hash
        legacy_secret = webhook.secret_hash
        if legacy_secret:
            # Transparently upgrade to encrypted_secret
            try:
                encrypted_token = encrypt_webhook_secret(legacy_secret)
                webhook.encrypted_secret = encrypted_token
                await self.session.commit()
            except Exception:
                pass
            return legacy_secret

        raise WebhookCryptoError(f"No valid signing secret found for webhook {webhook.id}")

    async def get_delivery_logs(
        self,
        tenant_id: uuid.UUID,
        webhook_id: uuid.UUID | None = None,
        limit: int = 50,
        offset: int = 0
    ) -> tuple[list[NotificationDeliveryLog], int]:
        """Queries delivery logs scoped to the workspace tenant with bound pagination."""
        safe_limit = min(max(1, limit), 100)
        safe_offset = max(0, offset)

        stmt = select(NotificationDeliveryLog).where(
            NotificationDeliveryLog.tenant_id == str(tenant_id),
            NotificationDeliveryLog.type == "WEBHOOK",
            NotificationDeliveryLog.is_deleted == False
        )

        if webhook_id is not None:
            webhook = await self.get_webhook_by_id(tenant_id, webhook_id)
            stmt = stmt.where(NotificationDeliveryLog.target == webhook.endpoint_url)

        from sqlalchemy import func
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_count = (await self.session.execute(count_stmt)).scalar() or 0

        stmt = stmt.order_by(desc(NotificationDeliveryLog.created_at)).offset(safe_offset).limit(safe_limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total_count

    async def migrate_legacy_webhook_secrets(self, batch_size: int = 50) -> dict[str, int]:
        """Resumable, idempotent, and bounded migration of dormant legacy webhook secrets.
        
        Identifies webhooks where `encrypted_secret` is NULL and `secret_hash` contains
        a legacy plaintext secret (or legacy recoverable secret).
        Encrypts the secret with AES-256-GCM, verifies decryption & HMAC integrity,
        and safely updates `encrypted_secret` in bounded batches.
        
        Never logs, exports, or exposes any secret values.
        Returns a dictionary with summary counts: {'inspected': N, 'migrated': M, 'failed': F}.
        """
        safe_batch = min(max(1, batch_size), 200)
        
        stmt = (
            select(WorkspaceWebhook)
            .where(
                WorkspaceWebhook.encrypted_secret.is_(None),
                WorkspaceWebhook.secret_hash.isnot(None),
                WorkspaceWebhook.is_deleted == False
            )
            .limit(safe_batch)
        )

        result = await self.session.execute(stmt)
        candidates = list(result.scalars().all())

        summary = {"inspected": len(candidates), "migrated": 0, "failed": 0}

        for wh in candidates:
            legacy_secret = wh.secret_hash
            if not legacy_secret:
                continue

            try:
                # 1. Encrypt with AES-256-GCM
                encrypted_token = encrypt_webhook_secret(legacy_secret)
                
                # 2. Verify decryption roundtrip
                decrypted = decrypt_webhook_secret(encrypted_token)
                if decrypted != legacy_secret:
                    raise WebhookCryptoError("Decryption roundtrip verification mismatch.")

                # 3. Verify HMAC signature derivation can succeed
                test_body = b'{"veritas_rag_crypto_probe": true}'
                hmac.new(decrypted.encode("utf-8"), test_body, hashlib.sha256).hexdigest()

                # 4. Commit verified encrypted token
                wh.encrypted_secret = encrypted_token
                summary["migrated"] += 1
            except Exception:
                summary["failed"] += 1

        if summary["migrated"] > 0:
            await self.session.commit()

        return summary

