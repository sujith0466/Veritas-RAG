import os

def write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Created {path}")

# 1. test_dedup_engine.py
test_dedup = '''"""Unit tests for DedupEngine."""

from uuid import uuid4
from backend.modules.retrieval.schemas.retrieval_dto import RankedEvidenceDTO
from backend.modules.retrieval.services.dedup_engine import DedupEngine

def create_evidence(content: str, score: float = 0.5) -> RankedEvidenceDTO:
    return RankedEvidenceDTO(
        chunk_id=uuid4(),
        document_id=uuid4(),
        document_version_id=uuid4(),
        tenant_id="test_tenant",
        content=content,
        rrf_score=score,
        final_rank=1,
    )

def test_sha256_dedup():
    engine = DedupEngine()
    c1 = create_evidence("Exact same content")
    c2 = create_evidence("Exact same content")
    c3 = create_evidence("Different content")
    
    deduped = engine.sha256_dedup([c1, c2, c3])
    assert len(deduped) == 2
    assert deduped[0].content == "Exact same content"
    assert deduped[1].content == "Different content"

def test_jaccard_near_dedup():
    engine = DedupEngine(jaccard_threshold=0.8)
    c1 = create_evidence("The quick brown fox jumps over the lazy dog", 0.9)
    c2 = create_evidence("The quick brown fox jumps over the lazy dog.", 0.5) # Punctuation diff
    c3 = create_evidence("A completely unrelated sentence about cats.", 0.3)
    
    deduped = engine.jaccard_dedup([c1, c2, c3])
    assert len(deduped) == 2
    assert deduped[0].rrf_score == 0.9 # Kept the higher score

def test_full_dedup_pipeline():
    engine = DedupEngine(jaccard_threshold=0.8)
    c1 = create_evidence("Same content exactly", 0.1)
    c2 = create_evidence("Same content exactly", 0.2)
    c3 = create_evidence("Same content exactly.", 0.9) # Near dup of the exact match
    c4 = create_evidence("Unique content.", 0.5)
    
    deduped, removed = engine.full_dedup_pipeline([c1, c2, c3, c4])
    assert removed == 2
    assert len(deduped) == 2
'''
write_file("tests/unit/backend/modules/retrieval/test_dedup_engine.py", test_dedup)

# 2. test_filter_dsl.py
test_filter = '''"""Unit tests for FilterDSL Compiler."""

import pytest
from datetime import datetime, timezone
from backend.modules.retrieval.schemas.filter_dsl import FilterDSL, DateRangeFilter
from backend.modules.retrieval.services.filter_dsl_compiler import FilterDSLCompiler
from backend.modules.retrieval.schemas.errors import TenantViolationError

def test_tenant_enforcement():
    compiler = FilterDSLCompiler()
    # No filter
    res = compiler.compile(None, "tenant1")
    assert res == {"tenant_id": "tenant1"}
    
    # Valid filter
    f = FilterDSL(tenant_id="tenant1", source_types=["pdf"])
    res = compiler.compile(f, "tenant1")
    assert res["tenant_id"] == "tenant1"
    assert res["source_types"] == ["pdf"]
    
    # Invalid filter (cross-tenant)
    f = FilterDSL(tenant_id="tenant2")
    with pytest.raises(TenantViolationError):
        compiler.compile(f, "tenant1")
        
def test_metadata_eq():
    compiler = FilterDSLCompiler()
    f = FilterDSL(metadata_eq={"department": "legal", "status": "active"})
    res = compiler.compile(f, "tenant1")
    assert res["metadata.department"] == "legal"
    assert res["metadata.status"] == "active"
'''
write_file("tests/unit/backend/modules/retrieval/test_filter_dsl.py", test_filter)

# 3. test_context_compressor.py
test_compressor = '''"""Unit tests for ContextCompressor."""

from uuid import uuid4
from backend.modules.retrieval.schemas.retrieval_dto import RankedEvidenceDTO
from backend.modules.retrieval.schemas.filter_dsl import CompressionOptionsDTO
from backend.modules.retrieval.services.context_compressor import ContextCompressor

def create_evidence(content: str) -> RankedEvidenceDTO:
    return RankedEvidenceDTO(
        chunk_id=uuid4(),
        document_id=uuid4(),
        document_version_id=uuid4(),
        tenant_id="test_tenant",
        content=content,
        rrf_score=0.5,
        final_rank=1,
    )

def test_sentence_extraction():
    options = CompressionOptionsDTO(enabled=True, max_tokens_per_chunk=10) # ~13 words
    compressor = ContextCompressor(options)
    
    long_content = "Word " * 20
    c = create_evidence(long_content)
    
    res = compressor.compress_candidates("query", [c])
    assert len(res) == 1
    assert "..." in res[0].compressed_content
    assert res[0].compression_ratio < 1.0

def test_disabled_compression():
    options = CompressionOptionsDTO(enabled=False)
    compressor = ContextCompressor(options)
    
    c = create_evidence("Some content")
    res = compressor.compress_candidates("query", [c])
    
    assert res[0].compressed_content is None
    assert res[0].compression_ratio is None
'''
write_file("tests/unit/backend/modules/retrieval/test_context_compressor.py", test_compressor)

print("Tests created.")
