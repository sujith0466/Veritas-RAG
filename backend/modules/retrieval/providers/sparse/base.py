"""Abstract base class interface for Sparse Keyword Search providers (`BaseSparseSearchProvider`).

Declares standard contracts for indexing chunk terms and executing sparse keyword matching
(such as `BM25`) while strictly enforcing multi-tenant isolation (`ADR-005`).
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from backend.modules.retrieval.schemas.retrieval_dto import CandidatePointDTO

if TYPE_CHECKING:
    from backend.modules.chunking.models.chunk import DocumentChunk


class BaseSparseSearchProvider(ABC):
    """Abstract interface for sparse keyword retrieval providers (`BM25`, `Splade`, etc.)."""

    @abstractmethod
    async def index_chunks(self, tenant_id: str, chunks: list["DocumentChunk"]) -> int:
        """Index or update a batch of document chunks into the sparse keyword index for the tenant.

        Args:
            tenant_id: Tenant namespace ID.
            chunks: List of DocumentChunk ORM instances to index.

        Returns:
            Number of chunks successfully indexed.
        """
        ...

    @abstractmethod
    async def search_keywords(
        self, tenant_id: str, query: str, limit: int = 50
    ) -> list[CandidatePointDTO]:
        """Execute sparse keyword matching (`BM25`) against the tenant index.

        Args:
            tenant_id: Tenant namespace ID (`ADR-005`).
            query: Sanitized search query text.
            limit: Maximum number of sparse candidates to retrieve.

        Returns:
            List of CandidatePointDTO ordered by descending sparse similarity score.
        """
        ...

    @abstractmethod
    async def remove_document_chunks(self, tenant_id: str, document_id: str) -> int:
        """Remove all indexed chunks for a given document from the tenant sparse index.

        Args:
            tenant_id: Tenant namespace ID.
            document_id: Document UUID string.

        Returns:
            Number of chunks removed.
        """
        ...
