from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select

from models.base import utcnow
from models.tables import FilingSection, ReviewQueue


def align_sections(current_filing_id: str, prior_filing_id: str, session, run_id: str) -> list[dict]:
    current_sections = _primary_sections(current_filing_id, session)
    prior_sections = _primary_sections(prior_filing_id, session)

    all_codes = set(current_sections) | set(prior_sections)
    pairs: list[dict] = []

    for code in all_codes:
        curr = current_sections.get(code)
        prev = prior_sections.get(code)

        if curr and prev:
            pairs.append(
                {
                    "section_code": code,
                    "current_section_id": str(curr.id),
                    "prior_section_id": str(prev.id),
                    "text_changed": curr.section_hash != prev.section_hash,
                    "confidence": 1.0,
                }
            )
        elif curr and not prev:
            _enqueue_section_review(
                session,
                "section_new_in_current",
                0.7,
                run_id,
                {
                    "section_code": code,
                    "current_filing_id": current_filing_id,
                    "prior_filing_id": prior_filing_id,
                    "current_section_id": str(curr.id),
                    "text_preview": curr.section_text[:300],
                },
            )
        elif prev and not curr:
            _enqueue_section_review(
                session,
                "section_removed_vs_prior",
                0.7,
                run_id,
                {
                    "section_code": code,
                    "current_filing_id": current_filing_id,
                    "prior_filing_id": prior_filing_id,
                    "prior_section_id": str(prev.id),
                    "text_preview": prev.section_text[:300],
                },
            )

    session.flush()
    return pairs


def _primary_sections(filing_id: str, session) -> dict[str, FilingSection]:
    rows = session.scalars(
        select(FilingSection).where(FilingSection.filing_id == filing_id).order_by(FilingSection.section_order)
    ).all()
    grouped: dict[str, list[FilingSection]] = defaultdict(list)
    for row in rows:
        if row.section_code:
            grouped[row.section_code].append(row)
    return {code: max(items, key=lambda section: len(section.section_text or "")) for code, items in grouped.items()}


def _enqueue_section_review(session, issue_type: str, confidence: float, run_id: str, details_json: dict) -> None:
    existing = session.scalar(
        select(ReviewQueue.id).where(
            ReviewQueue.object_type == "filing_section",
            ReviewQueue.issue_type == issue_type,
            ReviewQueue.details_json == details_json,
        )
    )
    if existing is not None:
        return
    session.add(
        ReviewQueue(
            object_type="filing_section",
            issue_type=issue_type,
            confidence=confidence,
            status="pending",
            source_run_id=run_id,
            details_json=details_json,
            created_at=utcnow(),
        )
    )
