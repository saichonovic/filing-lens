from __future__ import annotations

from sqlalchemy import select

from models.tables import (
    DetectedSignal,
    Filing,
    FilingSection,
    FinancialFact,
    Issuer,
    PolicyDisclosure,
    SignalEvidence,
)


DOCETL_GATE = {
    "accrual_divergence": "MEDIUM",
    "channel_stuffing": "MEDIUM",
    "covenant_stress": "MEDIUM",
    "going_concern_pre_signal": "LOW",
    "auditor_change": "LOW",
}

SEVERITY_RANK = {"CLEAN": 0, "LOW": 1, "WATCH": 1, "MEDIUM": 2, "HIGH": 3}

SIGNAL_SECTION_MAP = {
    "accrual_divergence": ["ITEM_7_MDA", "ITEM_2_MDA"],
    "channel_stuffing": ["ITEM_7_MDA", "ITEM_2_MDA"],
    "covenant_stress": ["FOOTNOTE_DEBT"],
    "going_concern_pre_signal": ["ITEM_7_MDA", "ITEM_2_MDA", "FOOTNOTE_GOING_CONCERN"],
}


def gate_passes(signal: DetectedSignal) -> bool:
    threshold = DOCETL_GATE.get(signal.signal_type)
    if not threshold:
        return False
    return SEVERITY_RANK.get(signal.severity, 0) >= SEVERITY_RANK.get(threshold, 2)


def get_section_texts(filing_id: str, session, codes: list[str]) -> dict[str, str]:
    sections = session.scalars(
        select(FilingSection).where(
            FilingSection.filing_id == filing_id,
            FilingSection.section_code.in_(codes),
        )
    ).all()
    return {section.section_code: (section.section_text or "")[:3000] for section in sections}


def get_signal_evidence(signal_id, session) -> list[dict]:
    rows = session.scalars(select(SignalEvidence).where(SignalEvidence.signal_id == signal_id)).all()
    payload: list[dict] = []
    for row in rows:
        detail = row.evidence_json or {}
        payload.append(
            {
                "label": detail.get("label", row.evidence_type),
                "value": float(row.numeric_value) if row.numeric_value is not None else None,
                "prior": float(row.comparison_value) if row.comparison_value is not None else None,
                "change_pct": detail.get("change_pct"),
                "quoted": row.quoted_text,
                "tier": detail.get("tier"),
                "detail": detail,
            }
        )
    return payload


def get_runway_months(filing_id: str, session) -> float | None:
    def get_fact(name: str) -> float | None:
        row = session.scalar(
            select(FinancialFact)
            .where(FinancialFact.filing_id == filing_id, FinancialFact.fact_name == name)
            .order_by(FinancialFact.confidence.desc(), FinancialFact.created_at.desc())
        )
        return float(row.fact_value_numeric) if row and row.fact_value_numeric is not None else None

    cash = get_fact("cash_and_equivalents")
    operating_cash_flow = get_fact("operating_cash_flow")
    if cash is None or operating_cash_flow is None or operating_cash_flow >= 0:
        return None
    return (cash / abs(operating_cash_flow)) * 12


def run_going_concern_narrative(signal: DetectedSignal, filing: Filing, issuer: Issuer, session) -> str | None:
    if not gate_passes(signal):
        return None
    from pipeline.docetl_runner import run_yaml_pipeline

    evidence = get_signal_evidence(signal.id, session)
    tier1_hits = [item["quoted"] for item in evidence if item.get("tier") == 1 and item.get("quoted")]
    tier2_hits = [item["quoted"] for item in evidence if item.get("tier") == 2 and item.get("quoted")]

    results = run_yaml_pipeline(
        "going_concern_hedge",
        [
            {
                "filing_id": str(filing.id),
                "ticker": issuer.ticker,
                "period_label": _period_label_for_filing(filing),
                "form_type": filing.form_type,
                "signal_severity": signal.severity,
                "signal_summary": signal.summary or "",
                "tier1_hits": tier1_hits,
                "tier2_hits": tier2_hits,
                "runway_months": get_runway_months(str(filing.id), session),
                "section_texts": get_section_texts(str(filing.id), session, SIGNAL_SECTION_MAP["going_concern_pre_signal"]),
            }
        ],
    )
    if not results:
        return None

    result = results[0]
    enriched = (
        (signal.summary or "")
        + f"\n\nANALYST NOTE: {result.get('narrative', '')}"
        + f"\n\nINVESTOR ACTION: {result.get('investor_action', '')}"
        + f"\n\nWATCH NEXT: {result.get('watch_next', '')}"
    )
    signal.summary = enriched
    signal.investor_question = result.get("investor_action", signal.investor_question)
    signal.detection_method = "llm_supported"
    session.flush()
    return enriched


def run_policy_change_narrative(
    policy: PolicyDisclosure,
    prior_filing_id: str | None,
    filing: Filing,
    issuer: Issuer,
    session,
) -> str | None:
    if not policy.is_new_vs_prior:
        return None
    from pipeline.docetl_runner import run_yaml_pipeline

    prior_text = "[No equivalent policy in prior filing]"
    if prior_filing_id:
        prior_policy = session.scalar(
            select(PolicyDisclosure).where(
                PolicyDisclosure.filing_id == prior_filing_id,
                PolicyDisclosure.policy_type == policy.policy_type,
            )
        )
        if prior_policy is not None and prior_policy.policy_text:
            prior_text = prior_policy.policy_text

    results = run_yaml_pipeline(
        "policy_change_narrative",
        [
            {
                "filing_id": str(filing.id),
                "ticker": issuer.ticker,
                "period_label": _period_label_for_filing(filing),
                "form_type": filing.form_type,
                "policy_type": policy.policy_type,
                "current_policy_text": policy.policy_text or "",
                "prior_policy_text": prior_text,
                "is_new_vs_prior": bool(policy.is_new_vs_prior),
            }
        ],
    )
    if not results:
        return None

    result = results[0]
    summary = (
        f"{result.get('change_explanation', '')}\n\n"
        f"Risk: {result.get('risk_implication', '')}\n\n"
        f"Question: {result.get('investor_question', '')}"
    )
    policy.change_summary = summary
    session.flush()
    return summary


def run_signal_narrative_enrichment(signal: DetectedSignal, filing: Filing, issuer: Issuer, session) -> str | None:
    if not gate_passes(signal) or signal.signal_type == "going_concern_pre_signal":
        return None
    from pipeline.docetl_runner import run_yaml_pipeline

    section_texts = get_section_texts(
        str(filing.id),
        session,
        SIGNAL_SECTION_MAP.get(signal.signal_type, ["ITEM_7_MDA"]),
    )
    section_text = "\n\n".join(text for text in section_texts.values() if text)
    results = run_yaml_pipeline(
        "signal_narrative_enrichment",
        [
            {
                "filing_id": str(filing.id),
                "ticker": issuer.ticker,
                "period_label": _period_label_for_filing(filing),
                "form_type": filing.form_type,
                "signal_type": signal.signal_type,
                "signal_family": signal.signal_family,
                "severity": signal.severity,
                "score": signal.score,
                "verdict": signal.verdict,
                "deterministic_summary": signal.summary or "",
                "investor_question": signal.investor_question,
                "evidence": get_signal_evidence(signal.id, session),
                "section_text": section_text,
            }
        ],
    )
    if not results:
        return None

    result = results[0]
    enriched = (
        (signal.summary or "")
        + f"\n\nANALYST NOTE: {result.get('analyst_note', '')}"
        + f"\n\nFOR INVESTORS: {result.get('plain_english', '')}"
        + f"\n\nWATCH NEXT: {result.get('watch_next', '')}"
    )
    signal.summary = enriched
    signal.detection_method = "llm_supported"
    session.flush()
    return enriched


def _period_label_for_filing(filing: Filing) -> str:
    if filing.period_end_date is not None:
        return filing.period_end_date.strftime("%Y-%m-%d")
    return filing.form_type
