from __future__ import annotations

from typing import Any

from sqlalchemy import delete, func, select

from models.tables import Filing, FilingComparison, Issuer, ReviewQueue
from pipeline.common import stage_run
from resolvers.fact_comparator import build_fact_comparison
from resolvers.policy_change_detector import detect_policy_changes
from resolvers.prior_filing_match import apply_prior_filing_resolution
from resolvers.section_aligner import align_sections


def run_resolve(issuer_id: str) -> dict[str, Any]:
    with stage_run("resolve", "issuer", issuer_id) as (session, run):
        counts = _run_resolve_in_existing_session(session, issuer_id, str(run.id))
        run.records_written = sum(counts.values())
        return {
            "run_id": str(run.id),
            "stage": run.stage_name,
            "issuer_id": issuer_id,
            **counts,
        }


def run_resolve_by_ticker(ticker: str) -> dict[str, Any]:
    with stage_run("resolve", "ticker", ticker) as (session, run):
        issuer = session.scalar(select(Issuer).where(Issuer.ticker == ticker))
        if issuer is None:
            raise ValueError(f"Issuer with ticker {ticker} not found.")
        counts = _run_resolve_in_existing_session(session, str(issuer.id), str(run.id))
        run.records_written = sum(counts.values())
        return {
            "run_id": str(run.id),
            "stage": run.stage_name,
            "issuer_id": str(issuer.id),
            "ticker": ticker,
            **counts,
        }


def _run_resolve_in_existing_session(session, issuer_id: str, run_id: str) -> dict[str, int]:
    _clear_existing_resolve_outputs(session, issuer_id)

    filings = session.scalars(
        select(Filing)
        .where(Filing.issuer_id == issuer_id)
        .order_by(Filing.period_end_date.desc(), Filing.filing_date.desc())
    ).all()

    counts = {"prior_matches": 0, "comparisons": 0, "section_pairs": 0, "policy_updates": 0, "review": 0}

    for filing in filings:
        prior, confidence = apply_prior_filing_resolution(str(filing.id), session, run_id)
        if prior is None:
            continue

        counts["prior_matches"] += 1
        comparison = build_fact_comparison(str(filing.id), str(prior.id), session)
        pairs = align_sections(str(filing.id), str(prior.id), session, run_id)
        comparison.summary_json["section_pairs"] = pairs
        session.add(comparison)
        session.flush()

        counts["comparisons"] += 1
        counts["section_pairs"] += len(pairs)
        counts["policy_updates"] += detect_policy_changes(str(filing.id), str(prior.id), session)

    counts["review"] = session.scalar(
        select(func.count()).select_from(ReviewQueue).where(ReviewQueue.source_run_id == run_id)
    ) or 0
    session.flush()
    return counts


def _clear_existing_resolve_outputs(session, issuer_id: str) -> None:
    filing_ids = session.scalars(select(Filing.id).where(Filing.issuer_id == issuer_id)).all()
    session.execute(
        delete(FilingComparison).where(FilingComparison.current_filing_id.in_(filing_ids))
    )
