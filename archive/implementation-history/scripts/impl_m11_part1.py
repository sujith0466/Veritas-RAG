import os
import sys

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

# ---------------------------------------------------------------------------
# Milestone 11.1: DTOs, Exceptions, ORM Models, and Alembic Migration
# ---------------------------------------------------------------------------
# This script creates:
# 1. New exceptions in schemas/errors.py
# 2. V2 DTOs in schemas/reflection_dto.py
# 3. ORM Model models/reflection_log.py
# 4. Repository repositories/reflection_repository.py
# 5. Alembic migration 0012_reflection_engine_v2.py

def main():
    print("Starting Milestone 11.1 Implementation...")

    # 1. Update backend/modules/reflection/schemas/errors.py
    errors_path = "backend/modules/reflection/schemas/errors.py"
    with open(errors_path, "r") as f:
        errors_content = f.read()

    if "ReflectionEvaluationFailed" not in errors_content:
        new_errors = """
class ReflectionEvaluationFailed(ReflectionDomainException):
    def __init__(self, message: str = "Reflection evaluation failed", detail: dict | None = None):
        super().__init__(message=message, error_code="REF_004", detail=detail)

class ContradictionDetectedError(ReflectionDomainException):
    def __init__(self, message: str = "Logical contradiction detected in claims", detail: dict | None = None):
        super().__init__(message=message, error_code="REF_005", detail=detail)
"""
        with open(errors_path, "a") as f:
            f.write(new_errors)
        print("Updated schemas/errors.py")
    else:
        print("schemas/errors.py already updated")

    # 2. Update backend/modules/reflection/schemas/reflection_dto.py
    dto_path = "backend/modules/reflection/schemas/reflection_dto.py"
    with open(dto_path, "r") as f:
        dto_content = f.read()

    if "ReflectionRequestDTOv2" not in dto_content:
        new_dtos = """
class CompletenessReportDTO(BaseModel):
    score: float = Field(..., ge=0.0, le=1.0, description="Ratio of addressed query requirements")
    addressed_clauses: list[str] = Field(default_factory=list)
    unaddressed_clauses: list[str] = Field(default_factory=list)

class LogicalReviewReportDTO(BaseModel):
    consistency_score: float = Field(..., ge=0.0, le=1.0, description="Score reflecting internal logical soundness")
    contradictions_found: list[str] = Field(default_factory=list)

class ReflectionRequestDTOv2(BaseModel):
    grounded_answer: GroundedAnswerDTO = Field(..., description="The generated grounded answer to reflect on")
    original_query: str = Field(..., description="The original user query text")
    correlation_id: str = Field(..., description="Request tracking ID")
    tenant_id: str = Field(..., description="Tenant namespace")

class ReflectionScoreDTO(BaseModel):
    hallucination_score: float = Field(..., ge=0.0, le=1.0)
    completeness_score: float = Field(..., ge=0.0, le=1.0)
    consistency_score: float = Field(..., ge=0.0, le=1.0)

class ReflectionResultDTOv2(BaseModel):
    correlation_id: str = Field(..., description="Request tracking ID")
    tenant_id: str = Field(..., description="Tenant namespace")
    overall_verdict: ClaimVerdict = Field(..., description="Worst-case verdict across all claims")
    scores: ReflectionScoreDTO = Field(..., description="Component reflection scores")
    claim_results: list[ClaimValidationResultDTO] = Field(default_factory=list)
    completeness_report: CompletenessReportDTO = Field(..., description="Query coverage breakdown")
    logical_report: LogicalReviewReportDTO = Field(..., description="Internal contradiction details")
    is_safe_to_serve: bool = Field(..., description="True if no severe issues detected")
    attempt_number: int = Field(1, description="Pass attempt number")
"""
        with open(dto_path, "a") as f:
            f.write(new_dtos)
        print("Updated schemas/reflection_dto.py")
    else:
        print("schemas/reflection_dto.py already updated")

    # 3. Create models/reflection_log.py
    os.makedirs("backend/modules/reflection/models", exist_ok=True)
    models_init = "backend/modules/reflection/models/__init__.py"
    if not os.path.exists(models_init):
        with open(models_init, "w") as f:
            f.write('"""Reflection ORM models."""\n')
            
    model_path = "backend/modules/reflection/models/reflection_log.py"
    if not os.path.exists(model_path):
        with open(model_path, "w") as f:
            f.write("""from sqlalchemy import Column, String, Float, Boolean, JSON, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime, timezone
from backend.core.database.engine import Base

class ReflectionLogORM(Base):
    __tablename__ = "reflection_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    correlation_id = Column(String(128), nullable=False, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    overall_verdict = Column(String(32), nullable=False)
    hallucination_score = Column(Float, nullable=False)
    completeness_score = Column(Float, nullable=False)
    consistency_score = Column(Float, nullable=False)
    is_safe_to_serve = Column(Boolean, nullable=False)
    attempt_number = Column(Integer, nullable=False, default=1)
    metadata_payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
""")
        print("Created models/reflection_log.py")
    else:
        print("models/reflection_log.py already exists")

    # 4. Create repositories/reflection_repository.py
    os.makedirs("backend/modules/reflection/repositories", exist_ok=True)
    repo_init = "backend/modules/reflection/repositories/__init__.py"
    if not os.path.exists(repo_init):
        with open(repo_init, "w") as f:
            f.write('"""Reflection repository module."""\n')
            
    repo_path = "backend/modules/reflection/repositories/reflection_repository.py"
    if not os.path.exists(repo_path):
        with open(repo_path, "w") as f:
            f.write("""from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.modules.reflection.models.reflection_log import ReflectionLogORM
from backend.modules.reflection.schemas.reflection_dto import ReflectionResultDTOv2

class ReflectionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_log(self, result: ReflectionResultDTOv2) -> ReflectionLogORM:
        log_entry = ReflectionLogORM(
            correlation_id=result.correlation_id,
            tenant_id=result.tenant_id,
            overall_verdict=result.overall_verdict,
            hallucination_score=result.scores.hallucination_score,
            completeness_score=result.scores.completeness_score,
            consistency_score=result.scores.consistency_score,
            is_safe_to_serve=result.is_safe_to_serve,
            attempt_number=result.attempt_number,
            metadata_payload={
                "claim_results": [c.model_dump(mode="json") for c in result.claim_results],
                "completeness_report": result.completeness_report.model_dump(mode="json"),
                "logical_report": result.logical_report.model_dump(mode="json")
            }
        )
        self.session.add(log_entry)
        await self.session.commit()
        await self.session.refresh(log_entry)
        return log_entry

    async def get_logs_by_correlation(self, correlation_id: str, tenant_id: str) -> list[ReflectionLogORM]:
        result = await self.session.execute(
            select(ReflectionLogORM)
            .where(ReflectionLogORM.correlation_id == correlation_id)
            .where(ReflectionLogORM.tenant_id == tenant_id)
            .order_by(ReflectionLogORM.attempt_number.asc())
        )
        return list(result.scalars().all())
""")
        print("Created repositories/reflection_repository.py")
    else:
        print("repositories/reflection_repository.py already exists")

    # 5. Create Alembic Migration
    migration_path = "alembic/versions/0012_reflection_engine_v2.py"
    if not os.path.exists(migration_path):
        with open(migration_path, "w") as f:
            f.write("""\"\"\"reflection_engine_v2

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-20 12:00:00.000000

\"\"\"
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0012'
down_revision: Union[str, None] = '0011'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('reflection_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('correlation_id', sa.String(length=128), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('overall_verdict', sa.String(length=32), nullable=False),
        sa.Column('hallucination_score', sa.Float(), nullable=False),
        sa.Column('completeness_score', sa.Float(), nullable=False),
        sa.Column('consistency_score', sa.Float(), nullable=False),
        sa.Column('is_safe_to_serve', sa.Boolean(), nullable=False),
        sa.Column('attempt_number', sa.Integer(), nullable=False),
        sa.Column('metadata_payload', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_reflection_logs_correlation_id'), 'reflection_logs', ['correlation_id'], unique=False)
    op.create_index(op.f('ix_reflection_logs_tenant_id'), 'reflection_logs', ['tenant_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_reflection_logs_tenant_id'), table_name='reflection_logs')
    op.drop_index(op.f('ix_reflection_logs_correlation_id'), table_name='reflection_logs')
    op.drop_table('reflection_logs')
""")
        print("Created migration 0012_reflection_engine_v2.py")
    else:
        print("Migration 0012_reflection_engine_v2.py already exists")

    print("Milestone 11.1 completed.")

if __name__ == "__main__":
    main()
