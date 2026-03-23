from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select

from models.base import utcnow
from models.tables import DetectedSignal, FinancialFact, SignalEvidence
from signals.common import replace_signal


HEADROOM_HIGH_RISK_PCT = Decimal("5")
HEADROOM_CAUTION_PCT = Decimal("15")


def run_covenant_stress_signal(filing_id: str, issuer_id: str, session) -> DetectedSignal | None:
    actual_ratio = _get_fact(filing_id, "covenant_leverage_ratio", session)
    ceiling = _get_fact(filing_id, "covenant_ceiling", session)
    headroom_usd = _get_fact(filing_id, "covenant_headroom_usd", session)

    if not actual_ratio or not ceiling or ceiling.fact_value_numeric <= 0:
        return None

    headroom_ratio = (ceiling.fact_value_numeric - actual_ratio.fact_value_numeric) / ceiling.fact_value_numeric * Decimal("100")
    if headroom_ratio <= HEADROOM_HIGH_RISK_PCT:
        severity, verdict, score = "HIGH", "HIGH_RISK", 9.0
    elif headroom_ratio <= HEADROOM_CAUTION_PCT:
        severity, verdict, score = "MEDIUM", "CAUTION", 6.0
    else:
        severity, verdict, score = "LOW", "WATCH", 2.0

    now = utcnow()
    summary = f"Leverage ratio {float(actual_ratio.fact_value_numeric):.2f}x vs ceiling {float(ceiling.fact_value_numeric):.2f}x. Headroom: {float(headroom_ratio):.1f}% of ceiling."
    signal = DetectedSignal(
        issuer_id=issuer_id,
        filing_id=filing_id,
        signal_type="covenant_stress",
        signal_family="liquidity_distress",
        severity=severity,
        score=score,
        verdict=verdict,
        status="active",
        detection_method="deterministic",
        summary=summary,
        investor_question=f"With leverage at {float(actual_ratio.fact_value_numeric):.1f}x against a {float(ceiling.fact_value_numeric):.1f}x ceiling, what is the contingency plan if EBITDA declines further?" if severity in ("HIGH", "MEDIUM") else None,
        created_at=now,
    )
    signal = replace_signal(signal, session)

    for row, label in [(actual_ratio, "covenant_actual"), (ceiling, "covenant_ceiling"), (headroom_usd, "headroom_usd")]:
        if row is None:
            continue
        session.add(
            SignalEvidence(
                signal_id=signal.id,
                evidence_type="numeric_fact",
                fact_id=row.id,
                numeric_value=row.fact_value_numeric,
                evidence_json={"label": label},
                created_at=now,
            )
        )

    session.flush()
    return signal


def _get_fact(filing_id: str, fact_name: str, session):
    return session.scalar(
        select(FinancialFact)
        .where(FinancialFact.filing_id == filing_id, FinancialFact.fact_name == fact_name)
        .order_by(FinancialFact.confidence.desc(), FinancialFact.created_at.desc())
    )
