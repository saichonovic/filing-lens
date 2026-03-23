from __future__ import annotations

from sqlalchemy import and_, select

from models.base import utcnow
from models.tables import Filing, FilingPeriod, ReviewQueue


def resolve_prior_filing(filing: Filing, session) -> tuple[Filing | None, float]:
    form_type = filing.form_type.replace("/A", "")
    if filing.fiscal_year is None:
        return None, 0.0

    prior = session.scalar(
        select(Filing)
        .where(
            and_(
                Filing.issuer_id == filing.issuer_id,
                Filing.form_type.in_([form_type, f"{form_type}/A"]),
                Filing.fiscal_year == filing.fiscal_year - 1,
                Filing.id != filing.id,
            )
        )
        .order_by(Filing.filing_date.desc())
    )
    if prior:
        return prior, 1.0

    if filing.period_end_date is None:
        return None, 0.0

    prior = session.scalar(
        select(Filing)
        .where(
            and_(
                Filing.issuer_id == filing.issuer_id,
                Filing.form_type.in_([form_type, f"{form_type}/A"]),
                Filing.period_end_date < filing.period_end_date,
                Filing.id != filing.id,
            )
        )
        .order_by(Filing.period_end_date.desc())
    )
    if not prior:
        return None, 0.0

    gap_days = (filing.period_end_date - prior.period_end_date).days
    expected_days = 365 if "10-K" in form_type else 90
    tolerance = 45
    if abs(gap_days - expected_days) <= tolerance:
        return prior, 0.85
    return prior, 0.6


def apply_prior_filing_resolution(filing_id: str, session, run_id: str) -> tuple[Filing | None, float]:
    filing = session.get(Filing, filing_id)
    if filing is None:
        raise ValueError(f"Filing {filing_id} not found.")

    prior, confidence = resolve_prior_filing(filing, session)
    if prior and confidence >= 0.75:
        periods = session.scalars(select(FilingPeriod).where(FilingPeriod.filing_id == filing_id)).all()
        for period in periods:
            period.comparable_prior_filing_id = prior.id
        session.flush()
        return prior, confidence

    if prior and confidence < 0.75:
        details = {
            "filing_id": filing_id,
            "candidate_prior_id": str(prior.id),
            "candidate_accession": prior.accession_number,
            "gap_days": (filing.period_end_date - prior.period_end_date).days if filing.period_end_date and prior.period_end_date else None,
        }
        existing = session.scalar(
            select(ReviewQueue.id).where(
                ReviewQueue.object_type == "filing_period",
                ReviewQueue.issue_type == "uncertain_prior_match",
                ReviewQueue.details_json == details,
            )
        )
        if existing is None:
            session.add(
                ReviewQueue(
                    object_type="filing_period",
                    issue_type="uncertain_prior_match",
                    confidence=confidence,
                    status="pending",
                    source_run_id=run_id,
                    details_json=details,
                    created_at=utcnow(),
                )
            )
        session.flush()
        return None, confidence

    return None, 0.0
