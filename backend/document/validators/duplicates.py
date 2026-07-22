"""Duplicate detection hooks (`VAL_006`)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.document.models.document import DocumentVersion
from backend.document.schemas.errors import (DocumentDomainException,
                                             DocumentErrorCode)


async def check_duplicate_content(
    content_hash: str,
    tenant_id: str,
    session: AsyncSession,
    reject_duplicates: bool = False,
) -> bool:
    """Verify whether a document with `content_hash` already exists in `tenant_id` namespace (`VAL_006`).

    Args:
        content_hash: SHA-256 stream checksum.
        tenant_id: Tenant namespace identifier.
        session: Active database session.
        reject_duplicates: If True, raises DocumentDomainException(VAL_006) on duplicate.

    Returns:
        True if duplicate exists, False otherwise.
    """
    stmt = (
        select(DocumentVersion.id)
        .join(DocumentVersion.document)
        .where(
            DocumentVersion.content_hash == content_hash,
            DocumentVersion.document.property.mapper.class_.tenant_id == tenant_id,
            DocumentVersion.document.property.mapper.class_.is_deleted.is_(False),
        )
        .limit(1)
    )
    result = await session.execute(stmt)
    existing_id = result.scalar_one_or_none()

    if existing_id is not None:
        if reject_duplicates:
            raise DocumentDomainException(
                code=DocumentErrorCode.VAL_006,
                message="Duplicate document content detected in this tenant namespace.",
                detail={
                    "content_hash": content_hash,
                    "existing_version_id": str(existing_id),
                },
            )
        return True

    return False
