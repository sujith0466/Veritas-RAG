import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

# ---------------------------------------------------------------------------
# Milestone 14.1: Schemas, Models, and Migrations for Knowledge Health
# ---------------------------------------------------------------------------

def main():
    print("Starting Milestone 14.1 Implementation...")
    
    # Create directories
    os.makedirs("backend/modules/health/schemas", exist_ok=True)
    os.makedirs("backend/modules/health/models", exist_ok=True)
    os.makedirs("backend/modules/health/repositories", exist_ok=True)
    os.makedirs("backend/modules/health/services", exist_ok=True)
    os.makedirs("backend/modules/health/tasks", exist_ok=True)
    os.makedirs("backend/modules/health/api", exist_ok=True)
    
    # 1. Create errors.py
    errors_path = "backend/modules/health/schemas/errors.py"
    if not os.path.exists(errors_path):
        with open(errors_path, "w") as f:
            f.write("""from enum import StrEnum
from backend.core.exceptions.base import RAGuardException

class HealthErrorCode(StrEnum):
    QUARANTINE_FAILED = "HLT_001"
    ANALYSIS_TIMEOUT = "HLT_002"

class HealthDomainException(RAGuardException):
    def __init__(self, message: str, error_code: str, detail: dict | None = None):
        super().__init__(message=message, error_code=error_code, detail=detail)
""")
        print("Created schemas/errors.py")

    # 2. Create health_dto.py
    dto_path = "backend/modules/health/schemas/health_dto.py"
    if not os.path.exists(dto_path):
        with open(dto_path, "w") as f:
            f.write("""from pydantic import BaseModel, Field
from enum import StrEnum

class IssueType(StrEnum):
    REDUNDANT = "REDUNDANT"
    CONTRADICTORY = "CONTRADICTORY"
    LOW_USAGE = "LOW_USAGE"
    OUTDATED = "OUTDATED"

class QuarantineAction(StrEnum):
    FLAG = "FLAG"
    SOFT_DELETE = "SOFT_DELETE"
    ARCHIVE = "ARCHIVE"

class DocumentIssueDTO(BaseModel):
    document_id: str = Field(...)
    issue_type: IssueType = Field(...)
    description: str = Field(...)
    severity: float = Field(..., ge=0.0, le=1.0)
    related_document_ids: list[str] = Field(default_factory=list)

class QuarantineRequestDTO(BaseModel):
    document_id: str = Field(...)
    action: QuarantineAction = Field(...)
    reason: str = Field(...)

class HealthReportDTO(BaseModel):
    tenant_id: str = Field(...)
    total_documents_analyzed: int = Field(...)
    issues_found: list[DocumentIssueDTO] = Field(default_factory=list)
    quarantined_documents: list[str] = Field(default_factory=list)
    health_score: float = Field(..., ge=0.0, le=100.0)
""")
        print("Created schemas/health_dto.py")

    # 3. Create ORM models
    with open("backend/modules/health/models/__init__.py", "w") as f:
        f.write('"""Health ORM models."""\n')

    model_path = "backend/modules/health/models/health_log.py"
    if not os.path.exists(model_path):
        with open(model_path, "w") as f:
            f.write("""from sqlalchemy import Column, String, Float, JSON, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime, timezone
from backend.database.base import Base

class HealthLogORM(Base):
    __tablename__ = "health_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String(64), nullable=False, index=True)
    health_score = Column(Float, nullable=False)
    issues_found_count = Column(Integer, nullable=False)
    metadata_payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

class QuarantineLogORM(Base):
    __tablename__ = "quarantine_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(String(128), nullable=False, index=True)
    action = Column(String(32), nullable=False)
    reason = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
""")
        print("Created models/health_log.py")

    # 4. Create Repository
    with open("backend/modules/health/repositories/__init__.py", "w") as f:
        f.write('"""Health repository module."""\n')

    repo_path = "backend/modules/health/repositories/health_repository.py"
    if not os.path.exists(repo_path):
        with open(repo_path, "w") as f:
            f.write("""from sqlalchemy.ext.asyncio import AsyncSession
from backend.modules.health.models.health_log import HealthLogORM, QuarantineLogORM
from backend.modules.health.schemas.health_dto import HealthReportDTO, QuarantineRequestDTO

class HealthRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_health_report(self, report: HealthReportDTO) -> HealthLogORM:
        log_entry = HealthLogORM(
            tenant_id=report.tenant_id,
            health_score=report.health_score,
            issues_found_count=len(report.issues_found),
            metadata_payload={
                "total_documents_analyzed": report.total_documents_analyzed,
                "issues": [i.model_dump(mode="json") for i in report.issues_found],
                "quarantined": report.quarantined_documents
            }
        )
        self.session.add(log_entry)
        await self.session.commit()
        await self.session.refresh(log_entry)
        return log_entry

    async def save_quarantine_action(self, request: QuarantineRequestDTO) -> QuarantineLogORM:
        log_entry = QuarantineLogORM(
            document_id=request.document_id,
            action=request.action,
            reason=request.reason
        )
        self.session.add(log_entry)
        await self.session.commit()
        await self.session.refresh(log_entry)
        return log_entry
""")
        print("Created repositories/health_repository.py")

    # 5. Create Alembic Migration 0015
    migration_path = "alembic/versions/0015_knowledge_health.py"
    if not os.path.exists(migration_path):
        with open(migration_path, "w") as f:
            f.write("""\"\"\"knowledge_health

Revision ID: 0015
Revises: 0014
Create Date: 2026-07-20 15:00:00.000000

\"\"\"
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0015'
down_revision: Union[str, None] = '0014'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table('health_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', sa.String(length=64), nullable=False),
        sa.Column('health_score', sa.Float(), nullable=False),
        sa.Column('issues_found_count', sa.Integer(), nullable=False),
        sa.Column('metadata_payload', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_health_logs_tenant_id'), 'health_logs', ['tenant_id'], unique=False)
    
    op.create_table('quarantine_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_id', sa.String(length=128), nullable=False),
        sa.Column('action', sa.String(length=32), nullable=False),
        sa.Column('reason', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_quarantine_logs_document_id'), 'quarantine_logs', ['document_id'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_quarantine_logs_document_id'), table_name='quarantine_logs')
    op.drop_table('quarantine_logs')
    op.drop_index(op.f('ix_health_logs_tenant_id'), table_name='health_logs')
    op.drop_table('health_logs')
""")
        print("Created migration 0015_knowledge_health.py")

    print("Milestone 14.1 completed.")

if __name__ == "__main__":
    main()
