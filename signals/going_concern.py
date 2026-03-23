from __future__ import annotations

import re

from sqlalchemy import select

from models.base import utcnow
from models.tables import DetectedSignal, FilingSection, FinancialFact, SignalEvidence
from signals.common import replace_signal


TIER1_PHRASES = [
    r"substantial\s+doubt\s+(?:exists\s+)?(?:about\s+)?(?:the\s+company'?s?\s+)?ability\s+to\s+continue\s+as\s+a\s+going\s+concern",
    r"going[\s-]+concern\s+(?:opinion|doubt|qualification|uncertainty)",
    r"raise[sd]?\s+substantial\s+doubt",
    r"ability\s+to\s+continue\s+as\s+a\s+going\s+concern",
    r"explanatory\s+paragraph\s+(?:relating\s+to|regarding)\s+going[\s-]+concern",
]

TIER2_PHRASES = [
    r"assumes?\s+(?:the\s+)?successful\s+completion\s+of",
    r"assumes?\s+(?:our|the\s+company'?s?)?\s+ability\s+to\s+(?:raise|obtain|secure)",
    r"fund\s+(?:our\s+)?(?:planned\s+)?operations\s+for\s+at\s+least\s+(?:the\s+next\s+)?12",
    r"will\s+be\s+sufficient\s+to\s+fund\s+(?:our\s+)?operations",
    r"if\s+we\s+(?:are\s+)?unable\s+to\s+(?:raise|obtain|generate|secure)",
    r"may\s+not\s+be\s+able\s+to\s+(?:raise|obtain|fund)",
    r"additional\s+(?:capital|financing|funding)\s+(?:may\s+be|will\s+be)?\s*(?:required|needed|necessary)",
    r"sufficiency\s+of\s+(?:our\s+)?cash\s+and\s+cash\s+equivalents\s+to\s+meet\s+(?:our\s+)?liquidity\s+needs",
    r"failure\s+to\s+obtain\s+additional\s+financing",
    r"access\s+capital\s+markets",
    r"repay\s+(?:our\s+)?existing\s+debt",
    r"significant\s+uncertainty\s+(?:exists\s+)?(?:about|regarding)",
]

LIQUIDITY_CONTEXT_PATTERNS = [
    r"\bgoing\s+concern\b",
    r"\bcontinue\s+operations?\b",
    r"\bfund\s+operations?\b",
    r"\bcash\s+and\s+cash\s+equivalents?\b",
    r"\bcash\b",
    r"\bliquidit(?:y|ies)\b",
    r"\bcapital\b",
    r"\bfinanc(?:e|ing)\b",
    r"\braise\s+(?:capital|funds|financing)\b",
    r"\bobtain\s+(?:capital|funding|financing)\b",
    r"\brepay\s+(?:our\s+)?(?:existing\s+)?debt\b",
    r"\bservice\s+(?:our\s+)?debt\b",
    r"\bmeet\s+(?:our\s+)?obligations\b",
    r"\brunway\b",
]

TARGET_SECTIONS = [
    "ITEM_8_FINANCIAL_STATEMENTS",
    "FOOTNOTE_GOING_CONCERN",
    "ITEM_7_MDA",
    "ITEM_2_MDA",
    "ITEM_1A_RISK_FACTORS",
]


def run_going_concern_signal(filing_id: str, issuer_id: str, session) -> DetectedSignal | None:
    sections = session.scalars(
        select(FilingSection)
        .where(
            FilingSection.filing_id == filing_id,
            FilingSection.section_code.in_(TARGET_SECTIONS),
        )
        .order_by(FilingSection.section_order)
    ).all()
    if not sections:
        return None

    tier1_hits: list[dict] = []
    tier2_hits: list[dict] = []
    tier2_pattern_hits: set[str] = set()

    for section in sections:
        text = section.section_text or ""
        for pattern in TIER1_PHRASES:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                sentence = _extract_sentence(text, match.start(), match.end())
                if not _has_liquidity_context(sentence):
                    continue
                tier1_hits.append(
                    {
                        "pattern": pattern,
                        "quoted": sentence,
                        "section": section,
                        "section_code": section.section_code,
                    }
                )

        for pattern in TIER2_PHRASES:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                sentence = _extract_sentence(text, match.start(), match.end())
                if not _has_liquidity_context(sentence):
                    continue
                tier2_pattern_hits.add(pattern)
                if any(hit["quoted"] == sentence for hit in tier2_hits):
                    continue
                tier2_hits.append(
                    {
                        "pattern": pattern,
                        "quoted": sentence,
                        "section": section,
                        "section_code": section.section_code,
                    }
                )

    if not tier1_hits and not tier2_hits:
        return None

    if tier1_hits:
        severity, score, verdict = "HIGH", 9.0, "HIGH_RISK"
        primary_hits = tier1_hits
    elif len(tier2_pattern_hits) >= 2:
        severity, score, verdict = "MEDIUM", 6.0, "CAUTION"
        primary_hits = tier2_hits
    else:
        severity, score, verdict = "LOW", 3.0, "WATCH"
        primary_hits = tier2_hits

    runway_months = _estimate_runway(filing_id, session)
    runway_note = ""
    if runway_months is not None:
        if runway_months < 6 and severity != "HIGH":
            severity, score, verdict = "HIGH", 9.0, "HIGH_RISK"
        elif runway_months < 12 and severity == "LOW":
            severity, score, verdict = "MEDIUM", 6.0, "CAUTION"
        elif runway_months < 18 and severity == "LOW":
            severity, score, verdict = "MEDIUM", 6.0, "CAUTION"
        runway_note = f" Estimated cash runway: ~{runway_months:.0f} months."

    top_quotes = [hit["quoted"] for hit in primary_hits[:2] if hit["quoted"]]
    summary = (
        f"Going-concern pre-signal detected. "
        f"Tier {'1' if tier1_hits else '2'} language found in {len(set(hit['section_code'] for hit in primary_hits))} section(s). "
        f"Tier 1 hits: {len(tier1_hits)}. Tier 2 hits: {len(tier2_hits)}. Distinct Tier 2 patterns: {len(tier2_pattern_hits)}.{runway_note}"
    )
    if top_quotes:
        summary += f'\nKey language: "{top_quotes[0]}"'

    signal = DetectedSignal(
        issuer_id=issuer_id,
        filing_id=filing_id,
        signal_type="going_concern_pre_signal",
        signal_family="liquidity_distress",
        severity=severity,
        score=score,
        verdict=verdict,
        status="active",
        detection_method="deterministic",
        summary=summary,
        investor_question=_build_investor_question(bool(tier1_hits), runway_months),
        created_at=utcnow(),
    )
    signal = replace_signal(signal, session)

    for hit in (tier1_hits + tier2_hits)[:5]:
        session.add(
            SignalEvidence(
                signal_id=signal.id,
                evidence_type="quoted_text",
                section_id=hit["section"].id,
                quoted_text=hit["quoted"][:500],
                evidence_json={
                    "tier": 1 if hit in tier1_hits else 2,
                    "section_code": hit["section_code"],
                    "pattern": hit["pattern"][:80],
                },
                created_at=utcnow(),
            )
        )

    session.flush()
    return signal


def _extract_sentence(text: str, match_start: int, match_end: int, window: int = 300) -> str:
    start = max(0, match_start - window)
    excerpt_before = text[start:match_start]
    sent_start = max(excerpt_before.rfind(". "), excerpt_before.rfind(".\n"), excerpt_before.rfind("\n\n"))
    if sent_start >= 0:
        start = start + sent_start + 2

    end = min(len(text), match_end + window)
    excerpt_after = text[match_end:end]
    sent_end = excerpt_after.find(". ")
    if sent_end >= 0:
        end = match_end + sent_end + 1
    return text[start:end].strip()


def _has_liquidity_context(text: str) -> bool:
    normalized = " ".join((text or "").split())
    return any(re.search(pattern, normalized, re.IGNORECASE) for pattern in LIQUIDITY_CONTEXT_PATTERNS)


def _estimate_runway(filing_id: str, session) -> float | None:
    def get_fact(name: str):
        row = session.scalar(
            select(FinancialFact)
            .where(FinancialFact.filing_id == filing_id, FinancialFact.fact_name == name)
            .order_by(FinancialFact.confidence.desc(), FinancialFact.created_at.desc())
        )
        return row.fact_value_numeric if row else None

    cash = get_fact("cash_and_equivalents")
    operating_cash_flow = get_fact("operating_cash_flow")
    if cash is None or operating_cash_flow is None or operating_cash_flow >= 0:
        return None
    annual_burn = abs(float(operating_cash_flow))
    if annual_burn == 0:
        return None
    return (float(cash) / annual_burn) * 12


def _build_investor_question(has_tier1_hits: bool, runway_months: float | None) -> str:
    if has_tier1_hits:
        return (
            "The filing uses going-concern language. What financing or operating milestones are required to continue operations beyond the next 12 months?"
        )
    if runway_months is not None and runway_months < 12:
        return (
            f"At the current burn rate, estimated cash runway is ~{runway_months:.0f} months. What financing actions are planned and on what timeline?"
        )
    return (
        "Management's liquidity language contains conditional financing assumptions. What funding is assumed in the operating plan, and what is the fallback if it is unavailable?"
    )
