from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select

from models.base import utcnow
from models.tables import DetectedSignal, FilingPeriod, FinancialFact, SignalEvidence
from signals.common import replace_signal


WATCH_THRESHOLD = Decimal("0.05")
HIGH_THRESHOLD = Decimal("0.10")


def run_accrual_signal(filing_id: str, issuer_id: str, period_id: str | None, session) -> DetectedSignal | None:
    accrual_row = _get_fact(filing_id, "accrual_ratio", session)
    ni_row = _get_fact(filing_id, "net_income", session)
    ocf_row = _get_fact(filing_id, "operating_cash_flow", session)
    assets_row = _get_fact(filing_id, "total_assets", session)

    if accrual_row is None:
        return None

    ratio = accrual_row.fact_value_numeric
    now = utcnow()

    if ratio > HIGH_THRESHOLD:
        severity, score, verdict = "HIGH", 9.0, "HIGH_RISK"
    elif ratio > WATCH_THRESHOLD:
        severity, score, verdict = "MEDIUM", 6.0, "CAUTION"
    elif ratio > Decimal("-0.02"):
        severity, score, verdict = "LOW", 3.0, "WATCH"
    else:
        severity, score, verdict = "CLEAN", 0.0, "CLEAN"

    prior_accrual = _get_prior_accrual(filing_id, session)
    yoy_shift = float(ratio - prior_accrual) if prior_accrual is not None else None
    if prior_accrual is not None and prior_accrual < 0 and ratio > 0 and severity == "LOW":
        severity, score, verdict = "MEDIUM", 5.0, "CAUTION"

    if severity == "CLEAN":
        return None

    signal = DetectedSignal(
        issuer_id=issuer_id,
        filing_id=filing_id,
        signal_type="accrual_divergence",
        signal_family="earnings_quality",
        severity=severity,
        score=score,
        verdict=verdict,
        status="active",
        detection_method="deterministic",
        summary=_build_summary(ratio, yoy_shift, severity),
        investor_question=_build_question(severity),
        created_at=now,
    )
    signal = replace_signal(signal, session)

    for row, label in [
        (accrual_row, "accrual_ratio"),
        (ni_row, "net_income"),
        (ocf_row, "operating_cash_flow"),
        (assets_row, "total_assets"),
    ]:
        if row is None:
            continue
        session.add(
            SignalEvidence(
                signal_id=signal.id,
                evidence_type="numeric_fact",
                fact_id=row.id,
                numeric_value=row.fact_value_numeric,
                comparison_value=prior_accrual if label == "accrual_ratio" and prior_accrual is not None else None,
                evidence_json={"label": label, "yoy_shift": yoy_shift},
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


def _get_prior_accrual(filing_id: str, session):
    period = session.scalar(select(FilingPeriod).where(FilingPeriod.filing_id == filing_id))
    if period is None or period.comparable_prior_filing_id is None:
        return None
    prior_row = session.scalar(
        select(FinancialFact).where(
            FinancialFact.filing_id == period.comparable_prior_filing_id,
            FinancialFact.fact_name == "accrual_ratio",
        )
    )
    return prior_row.fact_value_numeric if prior_row else None


def _build_summary(ratio, yoy_shift, severity: str) -> str:
    shift_str = f" YoY shift: {yoy_shift:+.4f}." if yoy_shift is not None else ""
    return f"Accrual ratio: {float(ratio):.4f}.{shift_str} Severity: {severity}."


def _build_question(severity: str) -> str:
    if severity in ("HIGH", "MEDIUM"):
        return "Net income is above operating cash flow. What is driving the gap between reported earnings and cash generation?"
    return "Accrual ratio crossed from negative to positive. Is this a timing difference or a structural earnings-quality shift?"
