from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from models.tables import DetectedSignal, Filing, FilingComparison, FilingPeriod, FinancialFact, Issuer, PolicyDisclosure, SignalEvidence


def build_issuer_report(issuer_id: str, session) -> dict:
    issuer = session.get(Issuer, issuer_id)
    filings = session.scalars(
        select(Filing).where(Filing.issuer_id == issuer_id).order_by(Filing.period_end_date.desc(), Filing.filing_date.desc())
    ).all()

    report = {
        "issuer": {"ticker": issuer.ticker, "name": issuer.name, "cik": issuer.cik},
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "filings": [],
    }

    for filing in filings:
        period = session.scalar(select(FilingPeriod).where(FilingPeriod.filing_id == filing.id))
        comparison = None
        if period and period.comparable_prior_filing_id:
            comp_row = session.scalar(
                select(FilingComparison).where(
                    FilingComparison.current_filing_id == filing.id,
                    FilingComparison.comparison_filing_id == period.comparable_prior_filing_id,
                )
            )
            if comp_row:
                comparison = {
                    "period_label": period.period_label,
                    "material_changes": comp_row.summary_json.get("material_changes", 0),
                    "flags": comp_row.summary_json.get("flags", []),
                }

        signals = session.scalars(
            select(DetectedSignal)
            .where(DetectedSignal.filing_id == filing.id, DetectedSignal.status == "active")
            .order_by(DetectedSignal.score.desc())
        ).all()

        signal_views = []
        for signal in signals:
            evidence = session.scalars(select(SignalEvidence).where(SignalEvidence.signal_id == signal.id)).all()
            signal_views.append(
                {
                    "signal_type": signal.signal_type,
                    "signal_family": signal.signal_family,
                    "severity": signal.severity,
                    "score": signal.score,
                    "verdict": signal.verdict,
                    "detection_method": signal.detection_method,
                    "summary": signal.summary,
                    "investor_question": signal.investor_question,
                    "evidence_count": len(evidence),
                    "evidence": [
                        {
                            "type": row.evidence_type,
                            "value": float(row.numeric_value) if row.numeric_value is not None else None,
                            "prior": float(row.comparison_value) if row.comparison_value is not None else None,
                            "detail": row.evidence_json,
                        }
                        for row in evidence
                    ],
                }
            )

        policies = session.scalars(select(PolicyDisclosure).where(PolicyDisclosure.filing_id == filing.id)).all()
        policy_views = [
            {
                "policy_type": policy.policy_type,
                "is_new_vs_prior": policy.is_new_vs_prior,
                "change_summary": policy.change_summary,
                "text_preview": (policy.policy_text or "")[:200],
            }
            for policy in policies
        ]

        report["filings"].append(
            {
                "accession_number": filing.accession_number,
                "form_type": filing.form_type,
                "period_label": period.period_label if period else None,
                "filing_date": filing.filing_date.isoformat(),
                "period_end_date": filing.period_end_date.isoformat() if filing.period_end_date else None,
                "facts": {
                    "revenue": _get_fact_value(session, filing.id, "revenue"),
                    "net_income": _get_fact_value(session, filing.id, "net_income"),
                    "operating_cash_flow": _get_fact_value(session, filing.id, "operating_cash_flow"),
                    "accrual_ratio": _get_fact_value(session, filing.id, "accrual_ratio"),
                    "dso": _get_fact_value(session, filing.id, "dso"),
                    "gross_margin_pct": _get_fact_value(session, filing.id, "gross_margin_pct"),
                },
                "comparison": comparison,
                "signals": signal_views,
                "policy_disclosures": policy_views,
                "overall_verdict": _overall_verdict(signal_views),
            }
        )

    return report


def _get_fact_value(session, filing_id, fact_name: str):
    row = session.scalar(
        select(FinancialFact)
        .where(FinancialFact.filing_id == filing_id, FinancialFact.fact_name == fact_name)
        .order_by(FinancialFact.confidence.desc(), FinancialFact.created_at.desc())
    )
    return float(row.fact_value_numeric) if row and row.fact_value_numeric is not None else None


def _overall_verdict(signal_views: list[dict]) -> str:
    severity_rank = {"CLEAN": 0, "LOW": 1, "WATCH": 1, "MEDIUM": 2, "HIGH": 3}
    if not signal_views:
        return "CLEAN"
    max_rank = max(severity_rank.get(signal["severity"], 0) for signal in signal_views)
    return {0: "CLEAN", 1: "WATCH", 2: "CAUTION", 3: "HIGH_RISK"}[max_rank]
