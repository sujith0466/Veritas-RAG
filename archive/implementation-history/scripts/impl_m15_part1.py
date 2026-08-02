import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

# ---------------------------------------------------------------------------
# Milestone 15.1: Schemas, Models, and Migrations for Evaluation Engine
# ---------------------------------------------------------------------------

def main():
    print("Starting Milestone 15.1 Implementation...")

    # Create directories
    os.makedirs("backend/modules/evaluation/schemas", exist_ok=True)
    os.makedirs("backend/modules/evaluation/models", exist_ok=True)
    os.makedirs("backend/modules/evaluation/repositories", exist_ok=True)
    os.makedirs("backend/modules/evaluation/services", exist_ok=True)
    os.makedirs("backend/modules/evaluation/api", exist_ok=True)

    # 1. Create errors.py
    errors_path = "backend/modules/evaluation/schemas/errors.py"
    if not os.path.exists(errors_path):
        with open(errors_path, "w") as f:
            f.write("""from enum import StrEnum
from backend.core.exceptions.base import RAGuardException

class EvaluationErrorCode(StrEnum):
    DATASET_NOT_FOUND = "EVAL_001"
    EVALUATION_FAILED = "EVAL_002"

class EvaluationDomainException(RAGuardException):
    def __init__(self, message: str, error_code: str, detail: dict | None = None):
        super().__init__(message=message, error_code=error_code, detail=detail)
""")
        print("Created schemas/errors.py")

    # 2. Create evaluation_dto.py
    dto_path = "backend/modules/evaluation/schemas/evaluation_dto.py"
    if not os.path.exists(dto_path):
        with open(dto_path, "w") as f:
            f.write("""from pydantic import BaseModel, Field

class GoldenExampleDTO(BaseModel):
    query: str = Field(...)
    expected_answer: str = Field(...)
    expected_document_ids: list[str] = Field(default_factory=list)

class DatasetCreateDTO(BaseModel):
    name: str = Field(...)
    tenant_id: str = Field(...)
    examples: list[GoldenExampleDTO] = Field(...)

class EvaluationResultDTO(BaseModel):
    dataset_id: str = Field(...)
    precision: float = Field(..., ge=0.0, le=1.0)
    recall: float = Field(..., ge=0.0, le=1.0)
    f1_score: float = Field(..., ge=0.0, le=1.0)
    average_reliability_score: float = Field(..., ge=0.0, le=100.0)
    total_examples: int = Field(...)
""")
        print("Created schemas/evaluation_dto.py")

    # 3. Create ORM models
    with open("backend/modules/evaluation/models/__init__.py", "w") as f:
        f.write('"""Evaluation ORM models."""\n')

    model_path = "backend/modules/evaluation/models/evaluation_log.py"
    if not os.path.exists(model_path):
        with open(model_path, "w") as f:
            f.write("""from sqlalchemy import Column, String, Float, JSON, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime, timezone
from backend.database.base import Base

class GoldenDatasetORM(Base):
    __tablename__ = "golden_datasets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String(64), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    examples = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

class EvaluationRunORM(Base):
    __tablename__ = "evaluation_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    precision = Column(Float, nullable=False)
    recall = Column(Float, nullable=False)
    f1_score = Column(Float, nullable=False)
    average_reliability_score = Column(Float, nullable=False)
    total_examples = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
""")
        print("Created models/evaluation_log.py")

    # 4. Create Repository
    with open("backend/modules/evaluation/repositories/__init__.py", "w") as f:
        f.write('"""Evaluation repository module."""\n')

    repo_path = "backend/modules/evaluation/repositories/evaluation_repository.py"
    if not os.path.exists(repo_path):
        with open(repo_path, "w") as f:
            f.write("""from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.modules.evaluation.models.evaluation_log import GoldenDatasetORM, EvaluationRunORM
from backend.modules.evaluation.schemas.evaluation_dto import DatasetCreateDTO, EvaluationResultDTO
import uuid

class EvaluationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_dataset(self, dto: DatasetCreateDTO) -> GoldenDatasetORM:
        dataset = GoldenDatasetORM(
            tenant_id=dto.tenant_id,
            name=dto.name,
            examples=[e.model_dump(mode="json") for e in dto.examples]
        )
        self.session.add(dataset)
        await self.session.commit()
        await self.session.refresh(dataset)
        return dataset

    async def get_dataset(self, dataset_id: str) -> GoldenDatasetORM | None:
        stmt = select(GoldenDatasetORM).where(GoldenDatasetORM.id == uuid.UUID(dataset_id))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def save_evaluation_run(self, result: EvaluationResultDTO) -> EvaluationRunORM:
        run = EvaluationRunORM(
            dataset_id=uuid.UUID(result.dataset_id),
            precision=result.precision,
            recall=result.recall,
            f1_score=result.f1_score,
            average_reliability_score=result.average_reliability_score,
            total_examples=result.total_examples
        )
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)
        return run
""")
        print("Created repositories/evaluation_repository.py")

    # 5. Create Alembic Migration 0016
    migration_path = "alembic/versions/0016_evaluation_engine.py"
    if not os.path.exists(migration_path):
        with open(migration_path, "w") as f:
            f.write("""\"\"\"evaluation_engine

Revision ID: 0016
Revises: 0015
Create Date: 2026-07-20 16:00:00.000000

\"\"\"
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0016'
down_revision: Union[str, None] = '0015'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table('golden_datasets',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('examples', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_golden_datasets_tenant_id'), 'golden_datasets', ['tenant_id'], unique=False)
    
    op.create_table('evaluation_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('dataset_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('precision', sa.Float(), nullable=False),
        sa.Column('recall', sa.Float(), nullable=False),
        sa.Column('f1_score', sa.Float(), nullable=False),
        sa.Column('average_reliability_score', sa.Float(), nullable=False),
        sa.Column('total_examples', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_evaluation_runs_dataset_id'), 'evaluation_runs', ['dataset_id'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_evaluation_runs_dataset_id'), table_name='evaluation_runs')
    op.drop_table('evaluation_runs')
    op.drop_index(op.f('ix_golden_datasets_tenant_id'), table_name='golden_datasets')
    op.drop_table('golden_datasets')
""")
        print("Created migration 0016_evaluation_engine.py")

    print("Milestone 15.1 completed.")

if __name__ == "__main__":
    main()
