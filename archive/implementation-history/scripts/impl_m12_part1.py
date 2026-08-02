import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

# ---------------------------------------------------------------------------
# Milestone 12.1: Schemas, Models, and Migrations for Validation Engine
# ---------------------------------------------------------------------------

def main():
    print("Starting Milestone 12.1 Implementation...")
    
    # Create directories
    os.makedirs("backend/modules/validation/schemas", exist_ok=True)
    os.makedirs("backend/modules/validation/models", exist_ok=True)
    os.makedirs("backend/modules/validation/repositories", exist_ok=True)
    os.makedirs("backend/modules/validation/services", exist_ok=True)
    os.makedirs("backend/modules/validation/providers", exist_ok=True)
    os.makedirs("backend/modules/validation/api", exist_ok=True)
    
    # 1. Create errors.py
    errors_path = "backend/modules/validation/schemas/errors.py"
    if not os.path.exists(errors_path):
        with open(errors_path, "w") as f:
            f.write("""from enum import StrEnum
from backend.core.exceptions.base import RAGuardException

class ValidationErrorCode(StrEnum):
    UNSUPPORTED_CLAIM = "VAL_001"
    INVALID_CITATION = "VAL_002"
    NLI_EVALUATION_FAILED = "VAL_003"
    ORCHESTRATION_FAILED = "VAL_004"

class ValidationDomainException(RAGuardException):
    def __init__(self, message: str, error_code: str, detail: dict | None = None):
        super().__init__(message=message, error_code=error_code, detail=detail)

class UnsupportedClaimError(ValidationDomainException):
    def __init__(self, message: str = "Claim lacks supporting evidence", detail: dict | None = None):
        super().__init__(message=message, error_code=ValidationErrorCode.UNSUPPORTED_CLAIM, detail=detail)

class InvalidCitationError(ValidationDomainException):
    def __init__(self, message: str = "Citation reference is invalid or missing", detail: dict | None = None):
        super().__init__(message=message, error_code=ValidationErrorCode.INVALID_CITATION, detail=detail)
""")
        print("Created schemas/errors.py")

    # 2. Create validation_dto.py
    dto_path = "backend/modules/validation/schemas/validation_dto.py"
    if not os.path.exists(dto_path):
        with open(dto_path, "w") as f:
            f.write("""from enum import StrEnum
from pydantic import BaseModel, Field
from backend.modules.generation.schemas.generation_dto import GroundedAnswerDTO

class EntailmentVerdict(StrEnum):
    ENTAILED = "ENTAILED"
    NEUTRAL = "NEUTRAL"
    CONTRADICTED = "CONTRADICTED"

class ClaimValidationItemDTO(BaseModel):
    claim_text: str = Field(..., description="The atomic claim extracted from the answer")
    citation_index: int | None = Field(None, description="The citation index it references")
    excerpt: str | None = Field(None, description="The excerpt used for NLI evaluation")
    verdict: EntailmentVerdict = Field(..., description="NLI evaluation verdict")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Model confidence in verdict")

class ValidationRequestDTO(BaseModel):
    grounded_answer: GroundedAnswerDTO = Field(..., description="The generated grounded answer")
    correlation_id: str = Field(..., description="Request tracking ID")
    tenant_id: str = Field(..., description="Tenant namespace")

class ValidationResultDTO(BaseModel):
    correlation_id: str = Field(..., description="Request tracking ID")
    tenant_id: str = Field(..., description="Tenant namespace")
    overall_verdict: EntailmentVerdict = Field(..., description="Aggregated worst-case verdict")
    entailment_ratio: float = Field(..., ge=0.0, le=1.0, description="Ratio of ENTAILED claims")
    unsupported_claim_count: int = Field(..., description="Number of NEUTRAL or CONTRADICTED claims")
    invalid_citation_count: int = Field(..., description="Number of claims referencing missing citations")
    claim_details: list[ClaimValidationItemDTO] = Field(default_factory=list)
    is_valid: bool = Field(..., description="True if no contradictions and entailment_ratio >= threshold")
""")
        print("Created schemas/validation_dto.py")

    # 3. Create ORM model validation_log.py
    with open("backend/modules/validation/models/__init__.py", "w") as f:
        f.write('"""Validation ORM models."""\n')

    model_path = "backend/modules/validation/models/validation_log.py"
    if not os.path.exists(model_path):
        with open(model_path, "w") as f:
            f.write("""from sqlalchemy import Column, String, Float, Boolean, JSON, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime, timezone
from backend.database.base import Base

class ValidationLogORM(Base):
    __tablename__ = "validation_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    correlation_id = Column(String(128), nullable=False, index=True)
    tenant_id = Column(String(64), nullable=False, index=True)
    overall_verdict = Column(String(32), nullable=False)
    entailment_ratio = Column(Float, nullable=False)
    unsupported_claim_count = Column(Integer, nullable=False)
    invalid_citation_count = Column(Integer, nullable=False)
    is_valid = Column(Boolean, nullable=False)
    metadata_payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
""")
        print("Created models/validation_log.py")

    # 4. Create Repository
    with open("backend/modules/validation/repositories/__init__.py", "w") as f:
        f.write('"""Validation repository module."""\n')

    repo_path = "backend/modules/validation/repositories/validation_repository.py"
    if not os.path.exists(repo_path):
        with open(repo_path, "w") as f:
            f.write("""from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.modules.validation.models.validation_log import ValidationLogORM
from backend.modules.validation.schemas.validation_dto import ValidationResultDTO

class ValidationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_log(self, result: ValidationResultDTO) -> ValidationLogORM:
        log_entry = ValidationLogORM(
            correlation_id=result.correlation_id,
            tenant_id=result.tenant_id,
            overall_verdict=result.overall_verdict,
            entailment_ratio=result.entailment_ratio,
            unsupported_claim_count=result.unsupported_claim_count,
            invalid_citation_count=result.invalid_citation_count,
            is_valid=result.is_valid,
            metadata_payload={
                "claim_details": [c.model_dump(mode="json") for c in result.claim_details]
            }
        )
        self.session.add(log_entry)
        await self.session.commit()
        await self.session.refresh(log_entry)
        return log_entry
""")
        print("Created repositories/validation_repository.py")

    # 5. Create Alembic Migration 0013
    migration_path = "alembic/versions/0013_answer_validation_schema.py"
    if not os.path.exists(migration_path):
        with open(migration_path, "w") as f:
            f.write("""\"\"\"answer_validation_schema

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-20 13:00:00.000000

\"\"\"
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0013'
down_revision: Union[str, None] = '0012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table('validation_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('correlation_id', sa.String(length=128), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('overall_verdict', sa.String(length=32), nullable=False),
        sa.Column('entailment_ratio', sa.Float(), nullable=False),
        sa.Column('unsupported_claim_count', sa.Integer(), nullable=False),
        sa.Column('invalid_citation_count', sa.Integer(), nullable=False),
        sa.Column('is_valid', sa.Boolean(), nullable=False),
        sa.Column('metadata_payload', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_validation_logs_correlation_id'), 'validation_logs', ['correlation_id'], unique=False)
    op.create_index(op.f('ix_validation_logs_tenant_id'), 'validation_logs', ['tenant_id'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_validation_logs_tenant_id'), table_name='validation_logs')
    op.drop_index(op.f('ix_validation_logs_correlation_id'), table_name='validation_logs')
    op.drop_table('validation_logs')
""")
        print("Created migration 0013_answer_validation_schema.py")

    print("Milestone 12.1 completed.")

if __name__ == "__main__":
    main()
