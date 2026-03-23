from __future__ import annotations

import hashlib
from datetime import datetime

from sqlalchemy import select

from models.tables import Filing, FilingDocument, Issuer
from parsers.sec_filing_index import fetch_filing_index
from pipeline.common import stage_run


def run_acquire(issuer: str, form_type: str, limit: int = 2) -> dict:
    """Register source artifacts. Deterministic only. No interpretation."""
    with stage_run(
        stage_name="acquire",
        scope_type="issuer",
        scope_id=issuer,
        config_snapshot={"form_type": form_type, "limit": limit},
    ) as (session, run):
        entries = fetch_filing_index(issuer, form_type, limit)
        if not entries:
            run.records_written = 0
            return {
                "run_id": str(run.id),
                "stage": run.stage_name,
                "issuer": issuer,
                "form_type": form_type,
                "limit": limit,
                "records_written": 0,
                "message": "No matching SEC filings found.",
            }

        first = entries[0]
        issuer_row = session.scalar(select(Issuer).where(Issuer.cik == first.cik))
        if issuer_row is None:
            issuer_row = Issuer(
                issuer_key=f"sec:{first.cik}",
                name=first.company_name,
                ticker=first.ticker,
                cik=first.cik,
                status="active",
            )
            session.add(issuer_row)
            session.flush()
            records_written = 1
        else:
            issuer_row.name = first.company_name
            issuer_row.ticker = first.ticker
            records_written = 0

        filings_written = 0
        documents_written = 0

        for entry in entries:
            filing = session.scalar(
                select(Filing).where(Filing.accession_number == entry.accession_number)
            )
            if filing is None:
                filing = Filing(
                    issuer_id=issuer_row.id,
                    accession_number=entry.accession_number,
                    form_type=entry.form_type,
                    filing_date=entry.filing_date,
                    period_end_date=datetime.strptime(entry.period_end_date, "%Y-%m-%d").date()
                    if entry.period_end_date
                    else None,
                    fiscal_year=(datetime.strptime(entry.period_end_date, "%Y-%m-%d").year if entry.period_end_date else None),
                    amendment_flag=entry.amendment_flag,
                    source_url=entry.source_url,
                    ingestion_status="raw",
                    content_hash=hashlib.sha256(entry.accession_number.encode("utf-8")).hexdigest(),
                )
                session.add(filing)
                session.flush()
                filings_written += 1

            document = session.scalar(
                select(FilingDocument).where(
                    FilingDocument.filing_id == filing.id,
                    FilingDocument.source_url == entry.source_url,
                )
            )
            if document is None:
                document = FilingDocument(
                    filing_id=filing.id,
                    document_role="primary",
                    source_format=entry.source_format,
                    source_url=entry.source_url,
                    mime_type=_mime_type(entry.source_format),
                    extraction_status="pending",
                )
                session.add(document)
                documents_written += 1

        run.records_written = records_written + filings_written + documents_written
        return {
            "run_id": str(run.id),
            "stage": run.stage_name,
            "issuer": issuer_row.ticker or issuer,
            "issuer_id": str(issuer_row.id),
            "form_type": form_type,
            "limit": limit,
            "records_written": run.records_written,
            "filings_written": filings_written,
            "documents_written": documents_written,
            "message": f"Registered {len(entries)} SEC filing metadata rows for {issuer_row.name}.",
        }


def _mime_type(source_format: str | None) -> str | None:
    if source_format == "htm" or source_format == "html":
        return "text/html"
    if source_format == "xml":
        return "application/xml"
    if source_format == "pdf":
        return "application/pdf"
    if source_format == "txt":
        return "text/plain"
    return None
