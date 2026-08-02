"""LLM Audit Repository for storing LLM telemetry."""

from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.modules.generation.models.llm_audit import LLMAuditRecord


class LLMAuditRepository:
    """Repository for LLMAuditRecord persistence."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        correlation_id: str | None,
        provider: str,
        model: str | None,
        mode: str,
        status: str,
        prompt_hash: str,
        prompt_text: str | None,
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
    ) -> LLMAuditRecord:
        """Create a new LLM audit record."""
        record = LLMAuditRecord(
            correlation_id=correlation_id,
            provider=provider,
            model=model,
            mode=mode,
            status=status,
            prompt_hash=prompt_hash,
            prompt_text=prompt_text,
            system_prompt_text=system_prompt_text,
            prompt_timestamp=prompt_timestamp,
            response_timestamp=response_timestamp,
            raw_response_text=raw_response_text,
            final_response_text=final_response_text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            error_message=error_message,
            metadata_payload=metadata_payload,
        )
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        return record
