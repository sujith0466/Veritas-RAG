"""Document domain events persistence repository (`DocumentEventRepository`).

Isolates append-only domain event logging for immutable auditing across the document lifecycle.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.document.models.event_log import DocumentEventLog


class DocumentEventRepository:
    """Repository for append-only domain event tracking."""

    async def append_event(
        self, event_log: DocumentEventLog, session: AsyncSession
    ) -> DocumentEventLog:
        """Persist a new domain event entry (`schema_version: "1.0.0"` payload format)."""
        session.add(event_log)
        await session.flush()
        await session.refresh(event_log)
        return event_log

    async def list_by_document(
        self, document_id: uuid.UUID, session: AsyncSession
    ) -> list[DocumentEventLog]:
        """Fetch all domain events emitted for a specific document, ordered chronologically."""
        stmt = (
            select(DocumentEventLog)
            .where(
                DocumentEventLog.document_id == document_id,
                DocumentEventLog.is_deleted.is_(False),
            )
            .order_by(DocumentEventLog.created_at.asc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())
