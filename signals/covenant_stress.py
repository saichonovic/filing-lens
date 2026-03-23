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

    if actual_ratio and ceiling and ceiling.fact_value_numeric > 0:
        return _build_leverage_signal(actual_ratio, ceiling, headroom_usd, filing_id, issuer_id, session)

    min_liquidity = _get_fact(filing_id, "covenant_min_liquidity", session)
    actual_liquidity = _get_fact(filing_id, "covenant_actual_liquidity", session)
    cash_fact = _get_fact(filing_id, "cash_and_equivalents", session)
    actual = actual_liquidity or cash_fact
    if min_liquidity and actual:
        return _build_liquidity_signal(min_liquidity, actual, filing_id, issuer_id, session)

    return None


def _build_leverage_signal(actual_ratio, ceiling, headroom_usd, filing_id: str, issuer_id: str, session) -> DetectedSignal:
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


def _build_liquidity_signal(min_liquidity, actual_liquidity, filing_id: str, issuer_id: str, session) -> DetectedSignal | None:
    min_val = float(min_liquidity.fact_value_numeric)
    actual_val = float(actual_liquidity.fact_value_numeric)
    if min_val <= 0:
        return None

    headroom_pct = ((actual_val - min_val) / min_val) * 100
    headroom_usd = actual_val - min_val
    if headroom_pct < 20:
        severity, verdict, score = "HIGH", "HIGH_RISK", 9.0
    elif headroom_pct < 50:
        severity, verdict, score = "MEDIUM", "CAUTION", 6.0
    elif headroom_pct < 100:
        severity, verdict, score = "LOW", "WATCH", 3.0
    else:
        return None

    now = utcnow()
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
        summary=(
            f"Minimum liquidity covenant: ${min_val:,.1f}M. "
            f"Actual cash: ${actual_val:,.1f}M. "
            f"Headroom: ${headroom_usd:,.1f}M ({headroom_pct:.0f}% above minimum)."
        ),
        investor_question=(
            f"Cash of ${actual_val:,.1f}M is only {headroom_pct:.0f}% above the "
            f"${min_val:,.1f}M minimum liquidity covenant. What is the current cash burn rate?"
        ),
        created_at=now,
    )
    signal = replace_signal(signal, session)
    for row, label in [(min_liquidity, "covenant_minimum"), (actual_liquidity, "actual_liquidity")]:
        if row is None:
            continue
        session.add(
            SignalEvidence(
                signal_id=signal.id,
                evidence_type="numeric_fact",
                fact_id=row.id,
                numeric_value=row.fact_value_numeric,
                evidence_json={
                    "label": label,
                    "headroom_usd": round(headroom_usd, 2),
                    "headroom_pct": round(headroom_pct, 1),
                },
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
