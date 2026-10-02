"""Add dispatch outbox state columns to processing_jobs.

Revision ID: d2_001_job_dispatch
Revises: chat_001_notif_logs
Create Date: 2026-10-02 03:20:00.000000+00:00

"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d2_001_job_dispatch"
down_revision: Union[str, None] = "chat_001_notif_logs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add dispatch tracking columns
    op.add_column(
        "processing_jobs",
        sa.Column(
            "dispatch_state",
            sa.String(length=50),
            server_default="PENDING_DISPATCH",
            nullable=False,
        ),
    )
    op.add_column(
        "processing_jobs",
        sa.Column("celery_task_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "processing_jobs",
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "processing_jobs",
        sa.Column("dispatch_error", sa.Text(), nullable=True),
    )

    # 2. Add index for dispatch state queries
    op.create_index(
        "ix_processing_jobs_dispatch_state",
        "processing_jobs",
        ["dispatch_state"],
        unique=False,
    )

    # 3. Backfill existing records safely
    # Active, completed, or formally failed jobs were acknowledged
    op.execute(
        """
        UPDATE processing_jobs
        SET dispatch_state = 'ACKNOWLEDGED'
        WHERE status IN ('COMPLETED', 'PROCESSED', 'CHUNKING', 'EMBEDDING', 'VECTOR_SYNC', 'READY')
           OR (status = 'FAILED' AND error_code IS NOT NULL);
        """
    )


def downgrade() -> None:
    op.drop_index("ix_processing_jobs_dispatch_state", table_name="processing_jobs")
    op.drop_column("processing_jobs", "dispatch_error")
    op.drop_column("processing_jobs", "dispatched_at")
    op.drop_column("processing_jobs", "celery_task_id")
    op.drop_column("processing_jobs", "dispatch_state")
