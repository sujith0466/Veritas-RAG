import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

# ---------------------------------------------------------------------------
# Milestone 13.1: Schemas, Models, and Migrations for Reliability Scoring
# ---------------------------------------------------------------------------

def main():
    print("Starting Milestone 13.1 Implementation...")
    
    # Create directories
    os.makedirs("backend/modules/scoring/schemas", exist_ok=True)
    os.makedirs("backend/modules/scoring/models", exist_ok=True)
    os.makedirs("backend/modules/scoring/repositories", exist_ok=True)
    os.makedirs("backend/modules/scoring/services", exist_ok=True)
    os.makedirs("backend/modules/scoring/api", exist_ok=True)
    
    # 1. Create errors.py
    errors_path = "backend/modules/scoring/schemas/errors.py"
    if not os.path.exists(errors_path):
        with open(errors_path, "w") as f:
            f.write("""from enum import StrEnum
from backend.core.exceptions.base import RAGuardException

class ScoringErrorCode(StrEnum):
    MISSING_INPUTS = "SCR_001"
    INVALID_WEIGHTS = "SCR_002"

class ScoringDomainException(RAGuardException):
    def __init__(self, message: str, error_code: str, detail: dict | None = None):
        super().__init__(message=message, error_code=error_code, detail=detail)

class MissingScoringInputsError(ScoringDomainException):
    def __init__(self, message: str = "Missing required inputs for scoring", detail: dict | None = None):
        super().__init__(message=message, error_code=ScoringErrorCode.MISSING_INPUTS, detail=detail)
""")
        print("Created schemas/errors.py")

    # 2. Create scoring_dto.py
    dto_path = "backend/modules/scoring/schemas/scoring_dto.py"
    if not os.path.exists(dto_path):
        with open(dto_path, "w") as f:
            f.write("""from pydantic import BaseModel, Field

class ScoringInputsDTO(BaseModel):
    retrieval_relevance_score: float = Field(..., ge=0.0, le=1.0)
    validation_entailment_ratio: float = Field(..., ge=0.0, le=1.0)
    confidence_evidence_strength: float = Field(..., ge=0.0, le=1.0)
    reflection_completeness: float = Field(..., ge=0.0, le=1.0)
    unsupported_claim_count: int = Field(0, ge=0)
    invalid_citation_count: int = Field(0, ge=0)

class ScoringRequestDTO(BaseModel):
    correlation_id: str = Field(..., description="Request tracking ID")
    tenant_id: str = Field(..., description="Tenant namespace")
    inputs: ScoringInputsDTO = Field(...)

class ReliabilityScoreDTO(BaseModel):
    correlation_id: str = Field(...)
    tenant_id: str = Field(...)
    final_score: float = Field(..., ge=0.0, le=100.0, description="Final reliability score 0-100")
    base_score: float = Field(..., ge=0.0, le=100.0)
    penalty_deduction: float = Field(..., ge=0.0)
    is_trusted: bool = Field(..., description="True if final_score >= 80 and no severe penalties")
    breakdown: dict = Field(default_factory=dict, description="Detailed score breakdown")
""")
        print("Created schemas/scoring_dto.py")

    # 3. Create ORM model scoring_log.py
    with open("backend/modules/scoring/models/__init__.py", "w") as f:
        f.write('"""Scoring ORM models."""\n')

    model_path = "backend/modules/scoring/models/scoring_log.py"
    if not os.path.exists(model_path):
        with open(model_path, "w") as f:
            f.write("""from sqlalchemy import Column, String, Float, Boolean, JSON, DateTime
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime, timezone
from backend.database.base import Base

class ScoringLogORM(Base):
    __tablename__ = "scoring_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    correlation_id = Column(String(128), nullable=False, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    final_score = Column(Float, nullable=False)
    is_trusted = Column(Boolean, nullable=False)
    metadata_payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
""")
        print("Created models/scoring_log.py")

    # 4. Create Repository
    with open("backend/modules/scoring/repositories/__init__.py", "w") as f:
        f.write('"""Scoring repository module."""\n')

    repo_path = "backend/modules/scoring/repositories/scoring_repository.py"
    if not os.path.exists(repo_path):
        with open(repo_path, "w") as f:
            f.write("""from sqlalchemy.ext.asyncio import AsyncSession
from backend.modules.scoring.models.scoring_log import ScoringLogORM
from backend.modules.scoring.schemas.scoring_dto import ReliabilityScoreDTO

class ScoringRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_log(self, result: ReliabilityScoreDTO) -> ScoringLogORM:
        log_entry = ScoringLogORM(
            correlation_id=result.correlation_id,
            tenant_id=result.tenant_id,
            final_score=result.final_score,
            is_trusted=result.is_trusted,
            metadata_payload={
                "base_score": result.base_score,
                "penalty_deduction": result.penalty_deduction,
                "breakdown": result.breakdown
            }
        )
        self.session.add(log_entry)
        await self.session.commit()
        await self.session.refresh(log_entry)
        return log_entry
""")
        print("Created repositories/scoring_repository.py")

    # 5. Create Alembic Migration 0014
    migration_path = "alembic/versions/0014_reliability_score.py"
    if not os.path.exists(migration_path):
        with open(migration_path, "w") as f:
            f.write("""\"\"\"reliability_score

Revision ID: 0014
Revises: 0013
Create Date: 2026-07-20 14:00:00.000000

\"\"\"
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0014'
down_revision: Union[str, None] = '0013'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table('scoring_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('correlation_id', sa.String(length=128), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('final_score', sa.Float(), nullable=False),
        sa.Column('is_trusted', sa.Boolean(), nullable=False),
        sa.Column('metadata_payload', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_scoring_logs_correlation_id'), 'scoring_logs', ['correlation_id'], unique=False)
    op.create_index(op.f('ix_scoring_logs_tenant_id'), 'scoring_logs', ['tenant_id'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_scoring_logs_tenant_id'), table_name='scoring_logs')
    op.drop_index(op.f('ix_scoring_logs_correlation_id'), table_name='scoring_logs')
    op.drop_table('scoring_logs')
""")
        print("Created migration 0014_reliability_score.py")

    print("Milestone 13.1 completed.")

if __name__ == "__main__":
    main()
