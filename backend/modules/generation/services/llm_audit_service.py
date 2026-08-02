"""LLM Audit Service for securely logging telemetry."""

from datetime import datetime
import hashlib
from typing import Any

from backend.core.config import get_settings
from backend.database.engine import get_session_factory
from backend.modules.generation.repositories.llm_audit_repository import (
    LLMAuditRepository,
)


class LLMAuditService:
    """Service to process and store LLM telemetry safely."""

    @staticmethod
    async def log_telemetry(
        correlation_id: str | None,
        provider: str,
        model: str | None,
        mode: str,
        status: str,
        prompt_text: str,
        system_prompt_text: str | None,
        prompt_timestamp: datetime,
        response_timestamp: datetime,
        raw_response_text: str | None,
        final_response_text: str | None,
        input_tokens: int | None,
        output_tokens: int | None,
        total_tokens: int | None,
        latency_ms: float,
        error_message: str | None,
        metadata_payload: dict[str, Any],
    ) -> None:
        """Process and asynchronously store telemetry without blocking chat."""
        settings = get_settings()
        audit_mode = getattr(settings.llm, "audit_mode", "hash_only")

        # 1. Always hash the prompt for exact matching/clustering
        full_prompt = f"{system_prompt_text or ''}\n{prompt_text}"
        prompt_hash = hashlib.sha256(full_prompt.encode("utf-8")).hexdigest()

        # 2. Preserve privacy based on config
        if audit_mode == "hash_only":
            prompt_to_store = None
            sys_prompt_to_store = None
            raw_response_to_store = None
            final_response_to_store = None
        else:
            prompt_to_store = prompt_text
            sys_prompt_to_store = system_prompt_text
            raw_response_to_store = raw_response_text
            final_response_to_store = final_response_text

        # 3. Store in DB
        try:
            async with get_session_factory()() as session:
                repo = LLMAuditRepository(session)
                await repo.create(
                    correlation_id=correlation_id,
                    provider=provider,
                    model=model,
                    mode=mode,
                    status=status,
                    prompt_hash=prompt_hash,
                    prompt_text=prompt_to_store,
                    system_prompt_text=sys_prompt_to_store,
                    prompt_timestamp=prompt_timestamp,
                    response_timestamp=response_timestamp,
                    raw_response_text=raw_response_to_store,
                    final_response_text=final_response_to_store,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    latency_ms=latency_ms,
                    error_message=error_message,
                    metadata_payload=metadata_payload,
                )
        except Exception as e:
            import structlog
            logger = structlog.get_logger(__name__)
            logger.error("Failed to persist LLM audit telemetry", error=str(e), correlation_id=correlation_id)

