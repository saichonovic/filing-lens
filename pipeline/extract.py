from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any

import requests
from sqlalchemy import delete, select

from app.config import settings
from extractors.section_parser import parse_sections
from models.tables import Filing, FilingComparison, FilingDocument, FilingPeriod, FilingSection, FinancialFact, PolicyDisclosure, ReviewQueue, SignalEvidence, DetectedSignal
from pipeline.common import stage_run


STORAGE_RAW = Path("storage/raw")


def run_extract(filing_id: str, force: bool = False) -> dict[str, Any]:
    """Download HTML and parse canonical filing sections. Deterministic only."""
    with stage_run("extract", "filing", filing_id, config_snapshot={"force": force}) as (session, run):
        result = _run_extract_in_existing_session(session, filing_id, run.id, force=force)
        run.records_written = result["downloaded"] + result["sections_committed"] + result["sections_queued"]
        return {
            "run_id": str(run.id),
            "stage": run.stage_name,
            **result,
            "message": "Extract stage completed with deterministic download and section parsing only.",
        }


def run_extract_all_pending(force: bool = False) -> list[dict[str, Any]]:
    scope_name = "all_force" if force else "all_pending"
    with stage_run("extract", "batch", scope_name, config_snapshot={"force": force}) as (session, run):
        query = select(Filing.id).join(FilingDocument, FilingDocument.filing_id == Filing.id)
        if force:
            query = query.where(FilingDocument.document_role == "primary")
        else:
            query = query.where(FilingDocument.extraction_status.in_(["pending", "downloaded"]))
        filing_ids = session.scalars(query.distinct()).all()

        results: list[dict[str, Any]] = []
        total_records = 0
        for filing_id in filing_ids:
            result = _run_extract_in_existing_session(session, str(filing_id), run.id, force=force)
            total_records += result["downloaded"] + result["sections_committed"] + result["sections_queued"]
            results.append(result)

        run.records_written = total_records
        return results


def _run_extract_in_existing_session(session, filing_id: str, run_id, force: bool = False) -> dict[str, Any]:
    filing = session.scalar(select(Filing).where(Filing.id == filing_id))
    if filing is None:
        raise ValueError(f"Filing {filing_id} was not found.")

    if force:
        _clear_existing_extract_outputs(session, filing.id)

    documents = session.scalars(
        select(FilingDocument).where(
            FilingDocument.filing_id == filing.id,
            FilingDocument.document_role == "primary",
        )
    ).all()

    downloaded = 0
    committed_sections = 0
    queued_sections = 0

    for document in documents:
        html_path, did_download = download_filing_document(document, filing, session)
        downloaded += int(did_download)

        sections = parse_sections(str(html_path), filing.id, document.id)
        committed, queued = commit_sections_with_review(session, sections, run_id)
        committed_sections += committed
        queued_sections += queued
        document.extraction_status = "sectioned"

    filing.ingestion_status = "extracted"
    return {
        "filing_id": str(filing.id),
        "downloaded": downloaded,
        "sections_committed": committed_sections,
        "sections_queued": queued_sections,
    }


def download_filing_document(doc: FilingDocument, filing: Filing, session) -> tuple[Path, bool]:
    headers = {
        "User-Agent": settings.sec_user_agent,
        "Accept-Encoding": "gzip, deflate",
    }

    accession_clean = filing.accession_number.replace("-", "")
    cik = filing.source_url.split("/data/")[1].split("/")[0] if filing.source_url and "/data/" in filing.source_url else "unknown"
    out_dir = STORAGE_RAW / cik / accession_clean
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "primary.html"

    if out_path.exists() and doc.content_hash:
        existing_hash = hashlib.sha256(out_path.read_bytes()).hexdigest()
        if existing_hash == doc.content_hash:
            doc.file_path = str(out_path)
            return out_path, False

    time.sleep(0.1)
    source_url = _normalize_archive_url(doc.source_url)
    response = requests.get(source_url, headers=headers, timeout=30)
    if response.status_code == 404:
        response = requests.get(_fallback_archive_url(filing, source_url), headers=headers, timeout=30)
    response.raise_for_status()

    out_path.write_bytes(response.content)
    doc.file_path = str(out_path)
    doc.source_url = response.url
    doc.content_hash = hashlib.sha256(response.content).hexdigest()
    doc.extraction_status = "downloaded"
    session.flush()
    return out_path, True


def commit_sections_with_review(session, sections: list[dict], run_id) -> tuple[int, int]:
    committed = 0
    queued = 0

    for section in sections:
        if section["confidence"] >= 0.7:
            existing = session.scalar(
                select(FilingSection).where(
                    FilingSection.filing_id == section["filing_id"],
                    FilingSection.document_id == section["document_id"],
                    FilingSection.section_code == section["section_code"],
                    FilingSection.section_hash == section["section_hash"],
                )
            )
            if existing is None:
                session.add(FilingSection(**section))
                committed += 1
        else:
            review_details = {
                "filing_id": str(section["filing_id"]),
                "section_code": section["section_code"],
                "section_title": section["section_title"],
                "section_hash": section["section_hash"],
                "text_preview": section["section_text"][:300],
            }
            existing_review = session.scalar(
                select(ReviewQueue).where(
                    ReviewQueue.object_type == "filing_section",
                    ReviewQueue.issue_type == "weak_section_alignment",
                    ReviewQueue.details_json["filing_id"].astext == str(section["filing_id"]),
                    ReviewQueue.details_json["section_code"].astext == section["section_code"],
                    ReviewQueue.details_json["section_title"].astext == section["section_title"],
                    ReviewQueue.details_json["text_preview"].astext == section["section_text"][:300],
                )
            )
            if existing_review is not None:
                continue
            session.add(
                ReviewQueue(
                    object_type="filing_section",
                    issue_type="weak_section_alignment",
                    confidence=section["confidence"],
                    status="pending",
                    source_run_id=run_id,
                    details_json=review_details,
                )
            )
            queued += 1

    session.flush()
    return committed, queued


def _clear_existing_extract_outputs(session, filing_id) -> None:
    signal_ids = session.scalars(select(DetectedSignal.id).where(DetectedSignal.filing_id == filing_id)).all()
    if signal_ids:
        session.execute(delete(SignalEvidence).where(SignalEvidence.signal_id.in_(signal_ids)))
    session.execute(delete(DetectedSignal).where(DetectedSignal.filing_id == filing_id))
    session.execute(
        delete(FilingComparison).where(
            FilingComparison.current_filing_id == filing_id
        )
    )
    session.execute(delete(FinancialFact).where(FinancialFact.filing_id == filing_id))
    session.execute(delete(PolicyDisclosure).where(PolicyDisclosure.filing_id == filing_id))
    session.execute(delete(FilingPeriod).where(FilingPeriod.filing_id == filing_id))
    session.execute(
        delete(ReviewQueue).where(
            ReviewQueue.object_type == "filing_section",
            ReviewQueue.details_json["filing_id"].astext == str(filing_id),
        )
    )
    session.execute(delete(FilingSection).where(FilingSection.filing_id == filing_id))


def _normalize_archive_url(source_url: str | None) -> str:
    if not source_url:
        raise ValueError("Missing source_url for filing document.")
    return source_url.replace("https://data.sec.gov/Archives", "https://www.sec.gov/Archives")


def _fallback_archive_url(filing: Filing, current_url: str) -> str:
    accession_clean = filing.accession_number.replace("-", "")
    cik = filing.source_url.split("/data/")[1].split("/")[0] if filing.source_url and "/data/" in filing.source_url else "unknown"
    return f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}/index.html"
