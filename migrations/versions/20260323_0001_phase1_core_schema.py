"""phase1 core schema

Revision ID: 20260323_0001
Revises: None
Create Date: 2026-03-23 15:45:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260323_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "issuers",
        sa.Column("issuer_key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("ticker", sa.String(length=16), nullable=True),
        sa.Column("cik", sa.String(length=16), nullable=True),
        sa.Column("exchange", sa.String(length=64), nullable=True),
        sa.Column("sector", sa.String(length=128), nullable=True),
        sa.Column("industry", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cik"),
        sa.UniqueConstraint("issuer_key"),
    )
    op.create_table(
        "analysis_runs",
        sa.Column("stage_name", sa.String(length=64), nullable=False),
        sa.Column("scope_type", sa.String(length=32), nullable=True),
        sa.Column("scope_id", sa.String(length=64), nullable=True),
        sa.Column("run_status", sa.String(length=32), nullable=False),
        sa.Column("records_written", sa.Integer(), nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("config_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "filings",
        sa.Column("issuer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("accession_number", sa.String(length=32), nullable=False),
        sa.Column("form_type", sa.String(length=16), nullable=False),
        sa.Column("filing_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end_date", sa.Date(), nullable=True),
        sa.Column("fiscal_year", sa.Integer(), nullable=True),
        sa.Column("fiscal_quarter", sa.Integer(), nullable=True),
        sa.Column("amendment_flag", sa.Boolean(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("ingestion_status", sa.String(length=32), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["issuer_id"], ["issuers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("accession_number", name="uq_filings_accession_number"),
    )
    op.create_table(
        "filing_documents",
        sa.Column("filing_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_role", sa.String(length=64), nullable=True),
        sa.Column("source_format", sa.String(length=16), nullable=True),
        sa.Column("file_path", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("mime_type", sa.String(length=64), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("word_count", sa.Integer(), nullable=True),
        sa.Column("ocr_required", sa.Boolean(), nullable=False),
        sa.Column("extraction_status", sa.String(length=32), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["filing_id"], ["filings.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "filing_sections",
        sa.Column("filing_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("section_code", sa.String(length=64), nullable=True),
        sa.Column("section_title", sa.String(length=256), nullable=True),
        sa.Column("section_order", sa.Integer(), nullable=True),
        sa.Column("section_text", sa.Text(), nullable=True),
        sa.Column("section_hash", sa.String(length=64), nullable=True),
        sa.Column("parent_section_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["filing_documents.id"]),
        sa.ForeignKeyConstraint(["filing_id"], ["filings.id"]),
        sa.ForeignKeyConstraint(["parent_section_id"], ["filing_sections.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "filing_periods",
        sa.Column("filing_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("period_type", sa.String(length=32), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("comparable_prior_filing_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("period_label", sa.String(length=32), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["comparable_prior_filing_id"], ["filings.id"]),
        sa.ForeignKeyConstraint(["filing_id"], ["filings.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "financial_facts",
        sa.Column("filing_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("period_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("fact_name", sa.String(length=128), nullable=False),
        sa.Column("fact_category", sa.String(length=64), nullable=True),
        sa.Column("fact_value_numeric", sa.Numeric(precision=24, scale=6), nullable=True),
        sa.Column("fact_value_text", sa.Text(), nullable=True),
        sa.Column("unit", sa.String(length=32), nullable=True),
        sa.Column("scale", sa.String(length=16), nullable=True),
        sa.Column("statement_type", sa.String(length=32), nullable=True),
        sa.Column("source_section_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_method", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["filing_id"], ["filings.id"]),
        sa.ForeignKeyConstraint(["period_id"], ["filing_periods.id"]),
        sa.ForeignKeyConstraint(["source_section_id"], ["filing_sections.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_facts_filing_name", "financial_facts", ["filing_id", "fact_name"], unique=False)
    op.create_table(
        "policy_disclosures",
        sa.Column("filing_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("section_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("policy_type", sa.String(length=64), nullable=True),
        sa.Column("policy_text", sa.Text(), nullable=True),
        sa.Column("is_new_vs_prior", sa.Boolean(), nullable=True),
        sa.Column("change_summary", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["filing_id"], ["filings.id"]),
        sa.ForeignKeyConstraint(["section_id"], ["filing_sections.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "review_queue",
        sa.Column("object_type", sa.String(length=64), nullable=False),
        sa.Column("object_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("issue_type", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("details_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["source_run_id"], ["analysis_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "detected_signals",
        sa.Column("issuer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filing_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("signal_type", sa.String(length=64), nullable=False),
        sa.Column("signal_family", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("verdict", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("detection_method", sa.String(length=32), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("investor_question", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["filing_id"], ["filings.id"]),
        sa.ForeignKeyConstraint(["issuer_id"], ["issuers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "signal_evidence",
        sa.Column("signal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_type", sa.String(length=64), nullable=False),
        sa.Column("section_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("fact_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("quoted_text", sa.Text(), nullable=True),
        sa.Column("numeric_value", sa.Numeric(precision=24, scale=6), nullable=True),
        sa.Column("comparison_value", sa.Numeric(precision=24, scale=6), nullable=True),
        sa.Column("evidence_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["fact_id"], ["financial_facts.id"]),
        sa.ForeignKeyConstraint(["section_id"], ["filing_sections.id"]),
        sa.ForeignKeyConstraint(["signal_id"], ["detected_signals.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("signal_evidence")
    op.drop_table("detected_signals")
    op.drop_table("review_queue")
    op.drop_table("policy_disclosures")
    op.drop_index("ix_facts_filing_name", table_name="financial_facts")
    op.drop_table("financial_facts")
    op.drop_table("filing_periods")
    op.drop_table("filing_sections")
    op.drop_table("filing_documents")
    op.drop_table("filings")
    op.drop_table("analysis_runs")
    op.drop_table("issuers")
