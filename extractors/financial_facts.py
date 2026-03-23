from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from models.base import utcnow
from models.tables import FinancialFact, ReviewQueue


DEBT_FOOTNOTE_RULES = [
    (
        "covenant_leverage_ratio",
        "ratio",
        r"(?:leverage\s+ratio|total\s+(?:net\s+)?leverage|consolidated\s+leverage)[^\d\n\(]{0,50}([\d.]+)\s*(?:to\s*1|x)",
        "ratio",
        "units",
    ),
    (
        "covenant_ceiling",
        "ratio",
        r"(?:not\s+(?:to\s+)?exceed|maximum(?:\s+permitted)?|must\s+not\s+exceed|covenant\s+(?:maximum|limit))[^\d\n\(]{0,30}([\d.]+)\s*(?:to\s*1|x)",
        "ratio",
        "units",
    ),
    (
        "covenant_min_liquidity",
        "ratio",
        r"minimum\s+(?:cash\s+)?liquidity\s+(?:requirement\s+)?of\s+\$?([\d,]+(?:\.\d+)?)\s*(?:million)?",
        "USD",
        "millions",
    ),
    (
        "covenant_actual_liquidity",
        "ratio",
        r"(?:had\s+)?(?:total\s+)?(?:cash(?:\s+and\s+cash\s+equivalents)?|liquidity)\s+of\s+\$?([\d,]+(?:\.\d+)?)\s*(?:million)?",
        "USD",
        "millions",
    ),
    (
        "covenant_headroom_usd",
        "ratio",
        r"(?:exceeds?[^\d\n]{0,30}(?:minimum|requirement|threshold)[^\d\n]{0,20}|headroom\s+of\s+|additional\s+(?:deterioration|decline)\s+of\s+approximately\s+)\$?\s*(\(?[\d,]+(?:\.\d+)?\)?)\s*(?:million)?",
        "USD",
        "millions",
    ),
    (
        "interest_coverage_ratio",
        "ratio",
        r"interest\s+coverage\s+ratio[^\d\n]{0,30}([\d.]+)\s*(?:to\s*1|x)",
        "ratio",
        "units",
    ),
    (
        "total_debt",
        "balance_sheet",
        r"(?:total\s+(?:long[\s-]?term\s+)?debt|aggregate\s+principal|outstanding\s+(?:principal\s+)?balance|debt\s+outstanding)[^\d\n\(]{0,50}\$?\s*(\(?[\d,]+(?:\.\d+)?\)?)",
        "USD",
        "millions",
    ),
    (
        "convertible_notes_payable",
        "balance_sheet",
        r"convertible\s+(?:senior\s+)?notes(?:\s+due\s+\d{4})?[^\d\n\(]{0,50}\$?\s*(\(?[\d,]+(?:\.\d+)?\)?)",
        "USD",
        "millions",
    ),
]

ALL_RULES = {
    "FOOTNOTE_DEBT": DEBT_FOOTNOTE_RULES,
}


def _parse_numeric(raw: str) -> Decimal | None:
    if not raw:
        return None
    s = raw.strip()
    negative = False
    if s.startswith("(") or s.startswith("$("):
        negative = True
    if s.endswith(")") and not s.startswith("("):
        negative = True
    cleaned = re.sub(r"[^0-9.]", "", s)
    if not cleaned:
        return None
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        return None
    return -value if negative else value


def extract_facts_from_section(section, period_id, session, rules_override=None) -> tuple[list[FinancialFact], list[ReviewQueue]]:
    rules = rules_override or ALL_RULES.get(section.section_code, [])
    if not rules:
        return [], []

    facts: list[FinancialFact] = []
    review_items: list[ReviewQueue] = []
    text = re.sub(r"\s+", " ", section.section_text or "")
    now = utcnow()

    for fact_name, category, pattern, unit, scale in rules:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if not matches:
            continue

        cleaned: list[Decimal] = []
        for match in matches:
            raw_value = match
            if isinstance(match, tuple):
                raw_value = next((part for part in match if part), None)
            if raw_value is None:
                continue
            value = _parse_numeric(str(raw_value))
            if value is None:
                continue
            cleaned.append(value)

        if not cleaned:
            continue

        primary_val = max(cleaned, key=lambda value: abs(value))
        confidence = Decimal("1.0") if len(set(cleaned)) == 1 else Decimal("0.8")

        fact = FinancialFact(
            filing_id=section.filing_id,
            period_id=period_id,
            fact_name=fact_name,
            fact_category=category,
            fact_value_numeric=primary_val,
            unit=unit,
            scale=scale,
            statement_type=category,
            source_section_id=section.id,
            source_method="regex",
            confidence=float(confidence),
            created_at=now,
        )

        if confidence >= Decimal("0.75"):
            facts.append(fact)
        else:
            review_items.append(
                ReviewQueue(
                    object_type="financial_fact",
                    issue_type="ambiguous_extraction",
                    confidence=float(confidence),
                    status="pending",
                    details_json={
                        "filing_id": str(section.filing_id),
                        "section_code": section.section_code,
                        "fact_name": fact_name,
                        "all_matches": [str(value) for value in cleaned],
                        "pattern": pattern,
                    },
                    created_at=now,
                )
            )

    return facts, review_items
