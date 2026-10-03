"""Normalize query analytics reliability_score to canonical 0.0-1.0 float scale.

Revision ID: ops_001_norm_score
Revises: d4_001_source_url
Create Date: 2026-10-03 12:30:00.000000+00:00

"""

from collections.abc import Sequence
from typing import Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "ops_001_norm_score"
down_revision: Union[str, None] = "d4_001_source_url"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Normalize legacy percentage-scale reliability scores (> 1.0) to canonical 0.0-1.0 float
    op.execute(
        """
        UPDATE query_analytics_records
        SET reliability_score = reliability_score / 100.0
        WHERE reliability_score > 1.0 AND reliability_score IS NOT NULL;
        """
    )


def downgrade() -> None:
    # Revert normalized reliability scores back to percentage scale where appropriate
    op.execute(
        """
        UPDATE query_analytics_records
        SET reliability_score = reliability_score * 100.0
        WHERE reliability_score <= 1.0 AND reliability_score IS NOT NULL;
        """
    )
