"""DNS Verification Celery Task."""

from datetime import UTC, datetime
import hashlib
from typing import Any
import uuid

from celery import shared_task
import dns.exception
import dns.resolver
from sqlalchemy import select
import structlog

from backend.models.entities.workspace_domain import WorkspaceDomain

logger = structlog.get_logger(__name__)

async def _verify_domain_async(domain_id: str, retries: int) -> bool:
    """Async execution for DNS verification."""
    from backend.core.dependencies.database import sessionmanager
    async with sessionmanager.session() as session:
        stmt = select(WorkspaceDomain).where(WorkspaceDomain.id == uuid.UUID(domain_id))
        result = await session.execute(stmt)
        domain = result.scalar_one_or_none()

        if not domain or domain.status != "VERIFYING":
            return False

        challenge_domain = f"_raguard-challenge.{domain.domain_name}"
        domain.dns_last_checked_at = datetime.now(UTC)

        try:
            # Synchronous DNS resolution via dnspython
            answers = dns.resolver.resolve(challenge_domain, "TXT", lifetime=5.0)

            for rdata in answers:
                for txt_string in rdata.strings:
                    txt_val = txt_string.decode("utf-8")
                    token_hash = hashlib.sha256(txt_val.encode("utf-8")).hexdigest()

                    if token_hash == domain.verification_token_hash:
                        domain.status = "VERIFIED"
                        domain.last_verified_at = datetime.now(UTC)
                        domain.error_reason = None
                        await session.commit()
                        logger.info("Domain verification successful", domain=domain.domain_name)
                        from backend.core.events import EventDispatcher
                        await EventDispatcher().dispatch("DOMAIN_VERIFIED", {"domain_id": str(domain.id), "workspace_id": str(domain.workspace_id)})
                        return True

            domain.error_reason = "TXT record found, but token hash mismatch."
            logger.warning("Domain verification failed: Hash mismatch", domain=domain.domain_name)

        except dns.resolver.NXDOMAIN as exc:
            domain.error_reason = f"NXDOMAIN: {exc!s}"
            logger.info("Domain verification pending: NXDOMAIN", domain=domain.domain_name)
            await session.commit()
            raise exc
        except dns.resolver.NoAnswer as exc:
            domain.error_reason = f"No TXT records found: {exc!s}"
            logger.info("Domain verification pending: NoAnswer", domain=domain.domain_name)
            await session.commit()
            raise exc
        except dns.exception.Timeout as exc:
            domain.error_reason = f"DNS resolution timeout: {exc!s}"
            logger.info("Domain verification timeout", domain=domain.domain_name)
            await session.commit()
            raise exc
        except Exception as exc:
            domain.error_reason = f"Unexpected error: {exc!s}"
            logger.error("Domain verification unexpected error", domain=domain.domain_name, error=str(exc))

        domain.status = "FAILED"
        await session.commit()
        from backend.core.events import EventDispatcher
        await EventDispatcher().dispatch("DOMAIN_FAILED", {"domain_id": str(domain.id), "workspace_id": str(domain.workspace_id), "reason": domain.error_reason})
        return False

@shared_task(bind=True, max_retries=5, default_retry_delay=1)
def trigger_dns_verification_task(self: Any, domain_id: str) -> None:
    """
    Worker for checking DNS TXT records.
    Retry Policy: 1s, 2s, 4s, 8s, 16s (Exponential Backoff).
    """
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        success = loop.run_until_complete(_verify_domain_async(domain_id, self.request.retries))
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.exception.Timeout) as exc:
        delay = 2 ** self.request.retries
        self.retry(exc=exc, countdown=delay)
    except Exception as exc:
        logger.error("Failed to execute DNS verification task", error=str(exc))
