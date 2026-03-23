"""add filing comparisons

Revision ID: 20260323_0003
Revises: 20260323_0002
Create Date: 2026-03-23 18:05:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260323_0003"
down_revision = "20260323_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "filing_comparisons",
        sa.Column("current_filing_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("comparison_filing_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("comparison_type", sa.String(length=32), nullable=False),
        sa.Column("summary_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["comparison_filing_id"], ["filings.id"]),
        sa.ForeignKeyConstraint(["current_filing_id"], ["filings.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("filing_comparisons")
