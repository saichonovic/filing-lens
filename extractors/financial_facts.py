from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from models.base import utcnow
from models.tables import FinancialFact, ReviewQueue


ALLOWED_PHASE1_SOURCE_METHODS = {"xbrl", "table_parse", "regex"}

INCOME_STATEMENT_RULES = [
    ("revenue", "income_stmt", r"(?:total\s+net\s+sales|total\s+revenue|total\s+sales)[^\d]{0,20}\$?\s*\(?\s*([\d,]+(?:\.\d+)?)", "USD", "millions"),
    ("gross_profit", "income_stmt", r"gross\s+(?:profit|margin)[^\d\n]{0,40}\$?\s*\(?\s*([\d,]+(?:\.\d+)?)", "USD", "millions"),
    ("operating_income", "income_stmt", r"(?:operating\s+income|income\s+from\s+operations)[^\d\n]{0,40}\$?\s*\(?\s*([\d,]+(?:\.\d+)?)", "USD", "millions"),
    ("net_income", "income_stmt", r"net\s+(?:income|earnings|loss)[^\d\n]{0,40}\$?\s*\(?\s*([\d,]+(?:\.\d+)?)", "USD", "millions"),
    ("diluted_eps", "income_stmt", r"diluted\s+\$?\s*([\d.]+)", "USD", "units"),
]

BALANCE_SHEET_RULES = [
    ("cash_and_equivalents", "balance_sheet", r"cash\s+and\s+(?:cash\s+)?equivalents[^\d\n]{0,40}\$?\s*\(?\s*([\d,]+(?:\.\d+)?)", "USD", "millions"),
    ("accounts_receivable", "balance_sheet", r"(?:accounts|trade)\s+receivable(?:,\s*net)?[^\d\n]{0,40}\$?\s*\(?\s*([\d,]+(?:\.\d+)?)", "USD", "millions"),
    ("inventory", "balance_sheet", r"inventor(?:y|ies)[^\d\n]{0,40}\$?\s*\(?\s*([\d,]+(?:\.\d+)?)", "USD", "millions"),
    ("total_assets", "balance_sheet", r"total\s+assets[^\d\n]{0,40}\$?\s*\(?\s*([\d,]+(?:\.\d+)?)", "USD", "millions"),
    ("total_debt", "balance_sheet", r"(?:total\s+debt|term\s+debt|long[\s-]?term\s+debt|notes\s+payable)[^\d\n]{0,40}\$?\s*\(?\s*([\d,]+(?:\.\d+)?)", "USD", "millions"),
    ("total_equity", "balance_sheet", r"total\s+(?:shareholders|stockholders)[’']?\s+equity[^\d\n]{0,40}\$?\s*\(?\s*([\d,]+(?:\.\d+)?)", "USD", "millions"),
]

CASH_FLOW_RULES = [
    ("operating_cash_flow", "cash_flow", r"(?:cash\s+generated\s+by\s+operating\s+activities|net\s+cash\s+(?:provided|used)\s+(?:by|in)\s+operating\s+activities)\s+\$?\s*\(?\s*([\d,]+(?:\.\d+)?)", "USD", "millions"),
    ("capex", "cash_flow", r"(?:capital\s+expenditures?|payments?\s+for\s+acquisition\s+of\s+property|purchases?\s+of\s+property)[^\d\n]{0,40}\$?\s*\(?\s*([\d,]+(?:\.\d+)?)", "USD", "millions"),
    ("free_cash_flow", "cash_flow", r"free\s+cash\s+flow[^\d\n]{0,40}\$?\s*\(?\s*([\d,]+(?:\.\d+)?)", "USD", "millions"),
]

DEBT_FOOTNOTE_RULES = [
    ("covenant_leverage_ratio", "ratio", r"(?:leverage\s+ratio|total\s+leverage)[^\d\n]{0,40}([\d.]+)\s*x", "ratio", "units"),
    ("covenant_ceiling", "ratio", r"(?:not\s+to\s+exceed|maximum)[^\d\n]{0,20}([\d.]+)\s*x", "ratio", "units"),
    ("covenant_headroom_usd", "ratio", r"(?:deterioration|decline)\s+of\s+approximately[^\d\n]{0,20}\$?\s*([\d,]+(?:\.\d+)?)", "USD", "millions"),
    ("interest_coverage_ratio", "ratio", r"interest\s+coverage\s+ratio[^\d\n]{0,30}([\d.]+)\s*x", "ratio", "units"),
]

ALL_RULES = {
    "ITEM_8_FINANCIAL_STATEMENTS": INCOME_STATEMENT_RULES + BALANCE_SHEET_RULES + CASH_FLOW_RULES,
    "ITEM_7_MDA": INCOME_STATEMENT_RULES[:3],
    "FOOTNOTE_DEBT": DEBT_FOOTNOTE_RULES,
    "ITEM_2_MDA": INCOME_STATEMENT_RULES[:3],
}


def extract_facts_from_section(section, period_id, session) -> tuple[list[FinancialFact], list[ReviewQueue]]:
    rules = ALL_RULES.get(section.section_code, [])
    if not rules:
        return [], []

    facts: list[FinancialFact] = []
    review_items: list[ReviewQueue] = []
    text = re.sub(r"\s+", " ", section.section_text)
    now = utcnow()

    for fact_name, category, pattern, unit, scale in rules:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if not matches:
            continue

        cleaned: list[Decimal] = []
        for match in matches:
            try:
                raw_value = match
                if isinstance(match, tuple):
                    raw_value = next((part for part in match if part), None)
                if raw_value is None:
                    continue
                cleaned.append(Decimal(str(raw_value).replace(",", "")))
            except (InvalidOperation, ValueError):
                continue

        if not cleaned:
            continue

        if section.section_code in {"ITEM_8_FINANCIAL_STATEMENTS", "ITEM_1_FINANCIAL_STATEMENTS"}:
            confidence = Decimal("1.0")
        elif len(cleaned) == 1 or len(set(cleaned)) == 1:
            confidence = Decimal("1.0")
        else:
            confidence = Decimal("0.6")

        primary_val = cleaned[0]
        if unit == "USD" and scale == "millions" and primary_val < 1:
            confidence = min(confidence, Decimal("0.8"))

        if confidence >= Decimal("0.75"):
            facts.append(
                FinancialFact(
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
            )
        else:
            review_items.append(
                ReviewQueue(
                    object_type="financial_fact",
                    issue_type="ambiguous_extraction" if len(set(cleaned)) > 1 else "scale_uncertainty",
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
