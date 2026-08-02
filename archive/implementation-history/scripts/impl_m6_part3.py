import os


def write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Created {path}")

# 1. alembic migration
migration = '''"""confidence_engine_v2

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-20

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'confidence_evaluations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', sa.String(50), nullable=False),
        sa.Column('query', sa.Text(), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('action', sa.String(20), nullable=False),
        sa.Column('coverage_score', sa.Float(), nullable=False),
        sa.Column('strength_score', sa.Float(), nullable=False),
        sa.Column('freshness_score', sa.Float(), nullable=False),
        sa.Column('conflict_score', sa.Float(), nullable=False),
        sa.Column('is_degraded', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('idx_confidence_evaluations_tenant_id', 'confidence_evaluations', ['tenant_id'])

def downgrade():
    op.drop_table('confidence_evaluations')
'''
write_file("alembic/versions/0010_confidence_engine_v2.py", migration)


# 2. Tests
test_coverage = '''"""Unit tests for Coverage Analyzer v2."""
from backend.modules.confidence.services.coverage_analyzer import CoverageAnalyzer
from backend.modules.retrieval.schemas.retrieval_dto import RankedEvidenceDTO
from uuid import uuid4

def test_extract_clauses():
    analyzer = CoverageAnalyzer()
    clauses = analyzer._extract_clauses("What is the capital of France, and who is the president?")
    assert len(clauses) == 2
    assert clauses[0] == "What is the capital of France"
    assert clauses[1] == "who is the president"

def test_token_overlap():
    analyzer = CoverageAnalyzer()
    score = analyzer._token_overlap("capital of France", "The capital of France is Paris.")
    assert score == 1.0
    
    score_low = analyzer._token_overlap("president of Germany", "The capital of France is Paris.")
    assert score_low < 0.5
'''
write_file("tests/unit/backend/modules/confidence/test_coverage_analyzer.py", test_coverage)


test_strength = '''"""Unit tests for Evidence Strength Scorer."""
from backend.modules.confidence.services.evidence_strength_scorer import EvidenceStrengthScorer
from backend.modules.retrieval.schemas.retrieval_dto import RankedEvidenceDTO
from uuid import uuid4

def create_evidence(rerank_score):
    return RankedEvidenceDTO(
        chunk_id=uuid4(),
        document_id=uuid4(),
        document_version_id=uuid4(),
        tenant_id="t1",
        content="test",
        rrf_score=0.9,
        rerank_score=rerank_score,
        final_rank=1
    )

def test_strength_scorer():
    scorer = EvidenceStrengthScorer()
    # 3 pieces of evidence, top_k 5
    ev = [create_evidence(0.9), create_evidence(0.8), create_evidence(0.85)]
    res = scorer.score(ev, top_k_requested=5)
    
    # 3 items -> corroboration = 1.0
    # citation_density = 3/5 = 0.6
    # rerank_conf = avg(0.9, 0.8, 0.85) = 0.85
    # auth = 0.7
    # (0.7*0.3) + (1.0*0.3) + (0.6*0.2) + (0.85*0.2) = 0.21 + 0.30 + 0.12 + 0.17 = 0.80
    assert res.corroboration_score == 1.0
    assert res.citation_density_score == 0.6
    assert round(res.strength_score, 2) == 0.80
'''
write_file("tests/unit/backend/modules/confidence/test_evidence_strength.py", test_strength)


test_engine = '''"""Unit tests for Confidence Engine v2."""
from backend.modules.confidence.services.confidence_engine import ConfidenceEngine
from backend.modules.confidence.schemas.confidence_dto import ConfidenceEvalRequestDTOv2, ConfidenceAction
from backend.modules.reliability.schemas.reliability_dto import ReliableRetrievalResultDTO
from backend.modules.retrieval.schemas.retrieval_dto import RankedEvidenceDTO, RetrievalStageBreakdownDTO
from uuid import uuid4

def test_confidence_engine_proceed():
    engine = ConfidenceEngine()
    ev = RankedEvidenceDTO(
        chunk_id=uuid4(), document_id=uuid4(), document_version_id=uuid4(),
        tenant_id="t1", content="The capital of France is Paris.",
        rrf_score=0.9, rerank_score=0.9, final_rank=1
    )
    
    ret_res = ReliableRetrievalResultDTO(
        query_text="What is the capital of France?",
        tenant_id="t1",
        correlation_id="123",
        top_k_requested=5,
        dense_candidates_count=10,
        sparse_candidates_count=10,
        unique_candidates_merged=15,
        final_evidence=[ev, ev, ev], # 3 for high corroboration
        stage_latencies=RetrievalStageBreakdownDTO(),
        is_degraded_fallback=False
    )
    
    req = ConfidenceEvalRequestDTOv2(
        query="What is the capital of France?",
        retrieval_result=ret_res,
        tenant_id="t1"
    )
    
    res = engine.evaluate(req)
    assert res.action == ConfidenceAction.PROCEED
    assert res.score > 75.0
'''
write_file("tests/unit/backend/modules/confidence/test_confidence_engine.py", test_engine)

print("impl_m6 part 3 (tests and migrations) completed.")
