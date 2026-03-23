"""add filing document content hash

Revision ID: 20260323_0002
Revises: 20260323_0001
Create Date: 2026-03-23 16:10:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260323_0002"
down_revision = "20260323_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("filing_documents", sa.Column("content_hash", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("filing_documents", "content_hash")
