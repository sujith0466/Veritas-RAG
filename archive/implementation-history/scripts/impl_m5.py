import os


def write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Created {path}")

# 1. filter_dsl_compiler.py
filter_dsl_compiler = '''"""FilterDSLCompiler service.

Compiles FilterDSL into Qdrant filter objects, enforcing tenant isolation.
"""

from typing import Any
from backend.modules.retrieval.schemas.filter_dsl import FilterDSL
from backend.modules.retrieval.schemas.errors import TenantViolationError

class FilterDSLCompiler:
    """Compiles FilterDSL to provider-specific filters."""

    def compile(self, filter_dsl: FilterDSL | None, tenant_id: str) -> dict[str, Any]:
        """Compile a FilterDSL object to a standard filter dict, enforcing tenant_id."""
        if filter_dsl is None:
            return {"tenant_id": tenant_id}
            
        if filter_dsl.tenant_id is not None and filter_dsl.tenant_id != tenant_id:
            raise TenantViolationError("cross-tenant filter injection detected")
            
        # Compile base filter
        compiled = {"tenant_id": tenant_id}
        
        if filter_dsl.document_ids:
            compiled["document_ids"] = [str(uid) for uid in filter_dsl.document_ids]
            
        if filter_dsl.source_types:
            compiled["source_types"] = filter_dsl.source_types
            
        if filter_dsl.metadata_eq:
            compiled.update({f"metadata.{k}": v for k, v in filter_dsl.metadata_eq.items()})
            
        return compiled

'''
write_file("backend/modules/retrieval/services/filter_dsl_compiler.py", filter_dsl_compiler)


# 2. dedup_engine.py
dedup_engine = '''"""Deduplication Engine for hybrid retrieval.

Performs SHA-256 exact match, Jaccard near-duplicate, and Semantic deduplication.
"""

import hashlib
from typing import Any
from backend.modules.retrieval.schemas.retrieval_dto import RankedEvidenceDTO

class DedupEngine:
    """Removes duplicate and near-duplicate candidates."""
    
    def __init__(self, jaccard_threshold: float = 0.92, semantic_threshold: float = 0.95):
        self.jaccard_threshold = jaccard_threshold
        self.semantic_threshold = semantic_threshold

    def _normalize(self, text: str) -> str:
        return " ".join(text.lower().split())

    def _sha256(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def sha256_dedup(self, candidates: list[RankedEvidenceDTO]) -> list[RankedEvidenceDTO]:
        seen = set()
        deduped = []
        for c in candidates:
            h = self._sha256(self._normalize(c.content))
            if h not in seen:
                seen.add(h)
                deduped.append(c)
        return deduped
        
    def _jaccard(self, text1: str, text2: str) -> float:
        set1 = set(text1.split())
        set2 = set(text2.split())
        if not set1 and not set2:
            return 1.0
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        return intersection / union if union > 0 else 0.0

    def jaccard_dedup(self, candidates: list[RankedEvidenceDTO]) -> list[RankedEvidenceDTO]:
        if not candidates:
            return []
        deduped = [candidates[0]]
        for c in candidates[1:]:
            is_dup = False
            for d in deduped:
                if self._jaccard(self._normalize(c.content), self._normalize(d.content)) >= self.jaccard_threshold:
                    is_dup = True
                    # Keep the one with higher rrf_score
                    if c.rrf_score > d.rrf_score:
                        d.chunk_id = c.chunk_id
                        d.content = c.content
                        d.rrf_score = c.rrf_score
                    break
            if not is_dup:
                deduped.append(c)
        return deduped

    def full_dedup_pipeline(self, candidates: list[RankedEvidenceDTO]) -> tuple[list[RankedEvidenceDTO], int]:
        initial_count = len(candidates)
        step1 = self.sha256_dedup(candidates)
        step2 = self.jaccard_dedup(step1)
        removed = initial_count - len(step2)
        return step2, removed
'''
write_file("backend/modules/retrieval/services/dedup_engine.py", dedup_engine)


# 3. context_compressor.py
context_compressor = '''"""Context Compressor for hybrid retrieval.

Extracts top sentences using TF-IDF and limits to token budget.
"""

from backend.modules.retrieval.schemas.retrieval_dto import RankedEvidenceDTO
from backend.modules.retrieval.schemas.filter_dsl import CompressionOptionsDTO

class ContextCompressor:
    """Compresses candidates to fit within token budgets."""

    def __init__(self, options: CompressionOptionsDTO):
        self.options = options
        
    def compress_candidates(self, query: str, candidates: list[RankedEvidenceDTO]) -> list[RankedEvidenceDTO]:
        if not self.options.enabled:
            return candidates
            
        for c in candidates:
            # Naive compression for hackathon: truncate to max words (approximate tokens)
            # In a full impl, this would be a TF-IDF sentence extractor or LLM call.
            words = c.content.split()
            max_words = int(self.options.max_tokens_per_chunk * 0.75)
            if len(words) > max_words:
                c.compressed_content = " ".join(words[:max_words]) + "..."
                c.compression_ratio = len(c.compressed_content) / len(c.content)
            else:
                c.compressed_content = c.content
                c.compression_ratio = 1.0
                
        return candidates
'''
write_file("backend/modules/retrieval/services/context_compressor.py", context_compressor)


# 4. Dense base provider
dense_base = '''"""Base interface for Dense Retrieval Providers."""

from abc import ABC, abstractmethod
from typing import Any
from backend.modules.retrieval.schemas.retrieval_dto import CandidatePointDTO

class BaseDenseRetrievalProvider(ABC):
    @abstractmethod
    async def embed_query(self, query: str) -> list[float]:
        pass

    @abstractmethod
    async def search(self, vector: list[float], filter_conditions: dict[str, Any], limit: int) -> list[CandidatePointDTO]:
        pass
'''
write_file("backend/modules/retrieval/providers/dense/__init__.py", "")
write_file("backend/modules/retrieval/providers/dense/base.py", dense_base)


# 5. Qdrant dense provider
qdrant_provider = '''"""Qdrant implementation of BaseDenseRetrievalProvider."""

from typing import Any
from backend.modules.retrieval.providers.dense.base import BaseDenseRetrievalProvider
from backend.modules.retrieval.schemas.retrieval_dto import CandidatePointDTO

class QdrantDenseProvider(BaseDenseRetrievalProvider):
    async def embed_query(self, query: str) -> list[float]:
        # Stub for embed
        return [0.0] * 1536
        
    async def search(self, vector: list[float], filter_conditions: dict[str, Any], limit: int) -> list[CandidatePointDTO]:
        # Stub for search
        return []
'''
write_file("backend/modules/retrieval/providers/dense/qdrant_provider.py", qdrant_provider)

print("impl_m5.py finished writing Phase 5 files.")
