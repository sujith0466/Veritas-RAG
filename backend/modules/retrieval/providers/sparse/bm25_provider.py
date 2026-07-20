"""BM25 Sparse Keyword Search Provider (`BM25SparseSearchProvider`).

Implements Okapi BM25 ranking algorithm with multi-tenant isolation,
memory-bounded LRU tenant caching (`max_tenants=500`), and tokenized term frequency
matching to satisfy exact term recall requirements.
"""

import math
import re
from collections import OrderedDict, Counter
from typing import TYPE_CHECKING, Any
from uuid import UUID

from structlog import get_logger

from backend.modules.retrieval.providers.sparse.base import BaseSparseSearchProvider
from backend.modules.retrieval.schemas.errors import SparseIndexNotFoundError
from backend.modules.retrieval.schemas.retrieval_dto import CandidatePointDTO

if TYPE_CHECKING:
    from backend.modules.chunking.models.chunk import DocumentChunk

logger = get_logger(__name__)

# Basic English stopword set for token normalization
STOPWORDS: set[str] = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any",
    "are", "aren't", "as", "at", "be", "because", "been", "before", "being", "below",
    "between", "both", "but", "by", "can", "cannot", "could", "did", "do", "does",
    "doing", "down", "during", "each", "few", "for", "from", "further", "had", "has",
    "have", "having", "he", "her", "here", "hers", "herself", "him", "himself", "his",
    "how", "i", "if", "in", "into", "is", "it", "its", "itself", "me", "more", "most",
    "my", "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or",
    "other", "our", "ours", "ourselves", "out", "over", "own", "same", "she", "should",
    "so", "some", "such", "than", "that", "the", "their", "theirs", "them", "themselves",
    "then", "there", "these", "they", "this", "those", "through", "to", "too", "under",
    "until", "up", "very", "was", "we", "were", "what", "when", "where", "which",
    "while", "who", "whom", "why", "with", "would", "you", "your", "yours", "yourself",
}


def tokenize(text: str) -> list[str]:
    """Tokenize and normalize text into lowercase alphanumeric terms excluding stopwords."""
    if not text:
        return []
    terms = re.findall(r"\b[a-z0-9_]{2,}\b", text.lower())
    return [t for t in terms if t not in STOPWORDS]


class _TenantBM25Index:
    """In-memory Okapi BM25 index for a specific tenant namespace."""

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.documents: dict[UUID, dict[str, Any]] = {}
        self.doc_term_counts: dict[UUID, Counter[str]] = {}
        self.doc_lengths: dict[UUID, int] = {}
        self.doc_term_freqs: dict[str, int] = {}
        self.avgdl: float = 0.0

    def add_document(
        self,
        chunk_id: UUID,
        document_id: UUID,
        document_version_id: UUID,
        tenant_id: str,
        content: str,
        metadata: dict[str, Any],
    ) -> None:
        """Index or re-index a document chunk."""
        if chunk_id in self.documents:
            self.remove_document(chunk_id)

        tokens = tokenize(content)
        length = len(tokens)
        counts = Counter(tokens)

        self.documents[chunk_id] = {
            "chunk_id": chunk_id,
            "document_id": document_id,
            "document_version_id": document_version_id,
            "tenant_id": tenant_id,
            "content": content,
            "metadata": metadata,
        }
        self.doc_term_counts[chunk_id] = counts
        self.doc_lengths[chunk_id] = length

        for term in counts.keys():
            self.doc_term_freqs[term] = self.doc_term_freqs.get(term, 0) + 1

        self._recompute_avgdl()

    def remove_document(self, chunk_id: UUID) -> bool:
        """Remove a document chunk from the index."""
        if chunk_id not in self.documents:
            return False

        counts = self.doc_term_counts.pop(chunk_id, Counter())
        for term in counts.keys():
            if term in self.doc_term_freqs:
                self.doc_term_freqs[term] -= 1
                if self.doc_term_freqs[term] <= 0:
                    self.doc_term_freqs.pop(term, None)

        self.doc_lengths.pop(chunk_id, None)
        self.documents.pop(chunk_id, None)
        self._recompute_avgdl()
        return True

    def _recompute_avgdl(self) -> None:
        if not self.doc_lengths:
            self.avgdl = 0.0
        else:
            self.avgdl = sum(self.doc_lengths.values()) / len(self.doc_lengths)

    def score(self, query_tokens: list[str]) -> list[tuple[UUID, float]]:
        """Compute BM25 scores across all indexed documents for the given query tokens."""
        N = len(self.documents)
        if N == 0 or not query_tokens:
            return []

        # Compute IDF for each query term
        idfs: dict[str, float] = {}
        for term in set(query_tokens):
            df = self.doc_term_freqs.get(term, 0)
            # Okapi BM25 IDF formula with +0.5 smoothing
            idf = math.log((N - df + 0.5) / (df + 0.5) + 1.0)
            idfs[term] = max(idf, 0.0)

        scores: list[tuple[UUID, float]] = []
        for chunk_id, doc_info in self.documents.items():
            counts = self.doc_term_counts[chunk_id]
            doc_len = self.doc_lengths[chunk_id]
            score = 0.0

            for term in query_tokens:
                if term not in counts:
                    continue
                tf = counts[term]
                idf = idfs.get(term, 0.0)
                # Okapi BM25 TF weight
                numerator = tf * (self.k1 + 1.0)
                denominator = tf + self.k1 * (
                    1.0 - self.b + self.b * (doc_len / max(self.avgdl, 1e-6))
                )
                score += idf * (numerator / denominator)

            if score > 0.0:
                scores.append((chunk_id, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores


class BM25SparseSearchProvider(BaseSparseSearchProvider):
    """In-memory Okapi BM25 sparse keyword search provider (`ADR-005`)."""

    def __init__(
        self,
        max_tenants: int = 500,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        self.max_tenants = max_tenants
        self.k1 = k1
        self.b = b
        self._indices: OrderedDict[str, _TenantBM25Index] = OrderedDict()

    def _get_or_create_index(self, tenant_id: str) -> _TenantBM25Index:
        if tenant_id in self._indices:
            self._indices.move_to_end(tenant_id)
            return self._indices[tenant_id]

        if len(self._indices) >= self.max_tenants:
            evicted_tenant, _ = self._indices.popitem(last=False)
            logger.info("Evicted LRU tenant sparse index", evicted_tenant=evicted_tenant)

        idx = _TenantBM25Index(k1=self.k1, b=self.b)
        self._indices[tenant_id] = idx
        return idx

    async def index_chunks(
        self, tenant_id: str, chunks: list["DocumentChunk"]
    ) -> int:
        """Index a batch of DocumentChunk objects for a tenant."""
        idx = self._get_or_create_index(tenant_id)
        indexed_count = 0

        for chunk in chunks:
            if str(chunk.tenant_id) != str(tenant_id):
                continue
            metadata = {
                "chunk_index": getattr(chunk, "chunk_index", 0),
                "strategy_used": getattr(chunk, "strategy_used", "unknown"),
                "token_count": getattr(chunk, "token_count", 0),
            }
            idx.add_document(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                document_version_id=chunk.document_version_id,
                tenant_id=tenant_id,
                content=chunk.content,
                metadata=metadata,
            )
            indexed_count += 1

        logger.debug(
            "Indexed chunks into BM25 sparse index",
            tenant_id=tenant_id,
            indexed_count=indexed_count,
            total_tenant_docs=len(idx.documents),
        )
        return indexed_count

    async def search_keywords(
        self, tenant_id: str, query: str, limit: int = 50
    ) -> list[CandidatePointDTO]:
        """Execute BM25 keyword matching for a tenant namespace."""
        if tenant_id not in self._indices:
            # If tenant index is not initialized in memory, raise RET_002 per taxonomy
            raise SparseIndexNotFoundError(
                f"Sparse BM25 index for tenant '{tenant_id}' is not initialized or found (`RET_002`)."
            )

        idx = self._indices[tenant_id]
        self._indices.move_to_end(tenant_id)

        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        scored_pairs = idx.score(query_tokens)
        top_pairs = scored_pairs[:limit]

        candidates: list[CandidatePointDTO] = []
        for rank, (chunk_id, score) in enumerate(top_pairs, start=1):
            doc = idx.documents[chunk_id]
            candidate = CandidatePointDTO(
                chunk_id=chunk_id,
                document_id=doc["document_id"],
                document_version_id=doc["document_version_id"],
                tenant_id=doc["tenant_id"],
                content=doc["content"],
                score=round(float(score), 6),
                source="sparse",
                rank=rank,
                metadata=doc["metadata"],
            )
            candidates.append(candidate)

        return candidates

    async def remove_document_chunks(
        self, tenant_id: str, document_id: str
    ) -> int:
        """Remove all chunks associated with a document_id from the tenant index."""
        if tenant_id not in self._indices:
            return 0

        idx = self._indices[tenant_id]
        to_remove = [
            cid
            for cid, doc in idx.documents.items()
            if str(doc["document_id"]) == str(document_id)
        ]
        removed_count = 0
        for cid in to_remove:
            if idx.remove_document(cid):
                removed_count += 1

        return removed_count
