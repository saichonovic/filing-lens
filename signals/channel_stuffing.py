from __future__ import annotations

from models.base import utcnow
from models.tables import DetectedSignal, FilingPeriod, FinancialFact, SignalEvidence
from signals.common import replace_signal


def run_channel_stuffing_signal(filing_id: str, issuer_id: str, prior_filing_id: str | None, session) -> DetectedSignal | None:
    if not prior_filing_id:
        return None

    score = 0
    triggered: list[str] = []
    evidence_rows: list[tuple] = []
    now = utcnow()

    curr_rev = _get_fact(filing_id, "revenue", session)
    prior_rev = _get_fact(prior_filing_id, "revenue", session)
    if curr_rev and prior_rev and prior_rev.fact_value_numeric > 0:
        rev_growth = float((curr_rev.fact_value_numeric - prior_rev.fact_value_numeric) / prior_rev.fact_value_numeric * 100)
        if rev_growth > 20:
            score += 3
            triggered.append(f"Revenue +{rev_growth:.1f}% YoY")
            evidence_rows.append((curr_rev, prior_rev, "revenue_spike", rev_growth))
        elif rev_growth > 10:
            score += 1
            triggered.append(f"Revenue +{rev_growth:.1f}% YoY (moderate)")

    curr_dso = _get_fact(filing_id, "dso", session)
    prior_dso = _get_fact(prior_filing_id, "dso", session)
    if curr_dso and prior_dso and prior_dso.fact_value_numeric > 0:
        dso_change_pct = float((curr_dso.fact_value_numeric - prior_dso.fact_value_numeric) / prior_dso.fact_value_numeric * 100)
        if dso_change_pct > 15:
            score += 3
            triggered.append(f"DSO +{dso_change_pct:.1f}% YoY")
            evidence_rows.append((curr_dso, prior_dso, "dso_rising", dso_change_pct))
        elif dso_change_pct > 8:
            score += 1
            triggered.append(f"DSO +{dso_change_pct:.1f}% YoY (moderate)")

    curr_inv = _get_fact(filing_id, "inventory_to_revenue_pct", session)
    prior_inv = _get_fact(prior_filing_id, "inventory_to_revenue_pct", session)
    if curr_inv and prior_inv and prior_inv.fact_value_numeric > 0:
        inv_change_pct = float((curr_inv.fact_value_numeric - prior_inv.fact_value_numeric) / prior_inv.fact_value_numeric * 100)
        if inv_change_pct > 25:
            score += 3
            triggered.append(f"Inventory/Revenue +{inv_change_pct:.1f}% YoY")
            evidence_rows.append((curr_inv, prior_inv, "inventory_build", inv_change_pct))
        elif inv_change_pct > 10:
            score += 1
            triggered.append(f"Inventory/Revenue +{inv_change_pct:.1f}% YoY (moderate)")

    if len(evidence_rows) == 3:
        score += 5

    if score < 2:
        return None

    if score >= 8:
        severity, verdict = "HIGH", "HIGH_RISK"
    elif score >= 4:
        severity, verdict = "MEDIUM", "CAUTION"
    else:
        severity, verdict = "LOW", "WATCH"

    signal = DetectedSignal(
        issuer_id=issuer_id,
        filing_id=filing_id,
        signal_type="channel_stuffing",
        signal_family="revenue_quality",
        severity=severity,
        score=float(score),
        verdict=verdict,
        status="active",
        detection_method="deterministic",
        summary=f"Channel stuffing score: {score}/14. Signals triggered: {'; '.join(triggered)}.",
        investor_question="Revenue growth is accompanied by rising DSO and/or inventory. What percentage of quarter-end sales included extended payment terms or return rights?" if severity in ("HIGH", "MEDIUM") else None,
        created_at=now,
    )
    signal = replace_signal(signal, session)

    for curr_row, prior_row, etype, change_val in evidence_rows:
        session.add(
            SignalEvidence(
                signal_id=signal.id,
                evidence_type=etype,
                fact_id=curr_row.id,
                numeric_value=curr_row.fact_value_numeric,
                comparison_value=prior_row.fact_value_numeric,
                evidence_json={
                    "change_pct": round(change_val, 2),
                    "current": float(curr_row.fact_value_numeric),
                    "prior": float(prior_row.fact_value_numeric),
                },
                created_at=now,
            )
        )

    session.flush()
    return signal


def _get_fact(filing_id: str, fact_name: str, session):
    from sqlalchemy import select
    return session.scalar(
        select(FinancialFact)
        .where(FinancialFact.filing_id == filing_id, FinancialFact.fact_name == fact_name)
        .order_by(FinancialFact.confidence.desc(), FinancialFact.created_at.desc())
    )
