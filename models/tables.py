from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utcnow


class Issuer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "issuers"

    issuer_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    ticker: Mapped[Optional[str]] = mapped_column(String(16))
    cik: Mapped[Optional[str]] = mapped_column(String(16), unique=True)
    exchange: Mapped[Optional[str]] = mapped_column(String(64))
    sector: Mapped[Optional[str]] = mapped_column(String(128))
    industry: Mapped[Optional[str]] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=utcnow)


class Filing(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "filings"
    __table_args__ = (UniqueConstraint("accession_number", name="uq_filings_accession_number"),)

    issuer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("issuers.id"), nullable=False)
    accession_number: Mapped[str] = mapped_column(String(32), nullable=False)
    form_type: Mapped[str] = mapped_column(String(16), nullable=False)
    filing_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end_date: Mapped[Optional[date]] = mapped_column(Date)
    fiscal_year: Mapped[Optional[int]]
    fiscal_quarter: Mapped[Optional[int]]
    amendment_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(Text)
    ingestion_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64))
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=utcnow)


class FilingDocument(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "filing_documents"

    filing_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("filings.id"), nullable=False)
    document_role: Mapped[Optional[str]] = mapped_column(String(64))
    source_format: Mapped[Optional[str]] = mapped_column(String(16))
    file_path: Mapped[Optional[str]] = mapped_column(Text)
    source_url: Mapped[Optional[str]] = mapped_column(Text)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64))
    mime_type: Mapped[Optional[str]] = mapped_column(String(64))
    page_count: Mapped[Optional[int]]
    word_count: Mapped[Optional[int]]
    ocr_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    extraction_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)


class AnalysisRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "analysis_runs"

    stage_name: Mapped[str] = mapped_column(String(64), nullable=False)
    scope_type: Mapped[Optional[str]] = mapped_column(String(32))
    scope_id: Mapped[Optional[str]] = mapped_column(String(64))
    run_status: Mapped[str] = mapped_column(String(32), default="running", nullable=False)
    records_written: Mapped[int] = mapped_column(default=0, nullable=False)
    error_summary: Mapped[Optional[str]] = mapped_column(Text)
    config_snapshot: Mapped[Optional[dict]] = mapped_column(JSONB)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class FilingSection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "filing_sections"

    filing_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("filings.id"), nullable=False)
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("filing_documents.id"))
    section_code: Mapped[Optional[str]] = mapped_column(String(64))
    section_title: Mapped[Optional[str]] = mapped_column(String(256))
    section_order: Mapped[Optional[int]]
    section_text: Mapped[Optional[str]] = mapped_column(Text)
    section_hash: Mapped[Optional[str]] = mapped_column(String(64))
    parent_section_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("filing_sections.id"))
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)


class FilingPeriod(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "filing_periods"

    filing_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("filings.id"), nullable=False)
    period_type: Mapped[str] = mapped_column(String(32), nullable=False)
    start_date: Mapped[Optional[date]] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    comparable_prior_filing_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("filings.id"))
    period_label: Mapped[Optional[str]] = mapped_column(String(32))


class FinancialFact(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "financial_facts"
    __table_args__ = (
        Index("ix_facts_filing_name", "filing_id", "fact_name"),
    )

    filing_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("filings.id"), nullable=False)
    period_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("filing_periods.id"))
    fact_name: Mapped[str] = mapped_column(String(128), nullable=False)
    fact_category: Mapped[Optional[str]] = mapped_column(String(64))
    fact_value_numeric: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 6))
    fact_value_text: Mapped[Optional[str]] = mapped_column(Text)
    unit: Mapped[Optional[str]] = mapped_column(String(32))
    scale: Mapped[Optional[str]] = mapped_column(String(16))
    statement_type: Mapped[Optional[str]] = mapped_column(String(32))
    source_section_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("filing_sections.id"))
    source_method: Mapped[str] = mapped_column(String(32), nullable=False, default="xbrl")
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)


class PolicyDisclosure(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "policy_disclosures"

    filing_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("filings.id"), nullable=False)
    section_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("filing_sections.id"))
    policy_type: Mapped[Optional[str]] = mapped_column(String(64))
    policy_text: Mapped[Optional[str]] = mapped_column(Text)
    is_new_vs_prior: Mapped[Optional[bool]] = mapped_column(Boolean)
    change_summary: Mapped[Optional[str]] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)


class FilingComparison(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "filing_comparisons"

    current_filing_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("filings.id"), nullable=False)
    comparison_filing_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("filings.id"), nullable=False)
    comparison_type: Mapped[str] = mapped_column(String(32), nullable=False)
    summary_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class ReviewQueue(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "review_queue"

    object_type: Mapped[str] = mapped_column(String(64), nullable=False)
    object_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    issue_type: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    source_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("analysis_runs.id"))
    details_json: Mapped[Optional[dict]] = mapped_column(JSONB)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class DetectedSignal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "detected_signals"

    issuer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("issuers.id"), nullable=False)
    filing_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("filings.id"))
    signal_type: Mapped[str] = mapped_column(String(64), nullable=False)
    signal_family: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    score: Mapped[Optional[float]] = mapped_column(Float)
    verdict: Mapped[Optional[str]] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    detection_method: Mapped[str] = mapped_column(String(32), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    investor_question: Mapped[Optional[str]] = mapped_column(Text)


class SignalEvidence(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "signal_evidence"

    signal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("detected_signals.id"), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False)
    section_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("filing_sections.id"))
    fact_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("financial_facts.id"))
    quoted_text: Mapped[Optional[str]] = mapped_column(Text)
    numeric_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 6))
    comparison_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 6))
    evidence_json: Mapped[Optional[dict]] = mapped_column(JSONB)
