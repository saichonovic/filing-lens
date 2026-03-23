from __future__ import annotations

import re

from models.base import utcnow
from models.tables import PolicyDisclosure


POLICY_PATTERNS = [
    ("revenue_recognition", r"revenue\s+recognition", 2000),
    ("bill_and_hold", r"bill.and.hold|customer.requested\s+holding|risk\s+of\s+ownership", 1000),
    ("expense_capitalization", r"capitaliz(?:e|ation)\s+(?:of\s+)?(?:software|internal.use|development\s+costs|network)", 1000),
    ("going_concern_assumption", r"(?:substantial\s+doubt|going\s+concern|ability\s+to\s+continue)", 1500),
    ("liquidity_assumption", r"(?:sufficient\s+to\s+fund|fund\s+operations\s+for\s+at\s+least|assumes\s+successful\s+completion)", 1000),
]

POLICY_SECTIONS = {
    "ITEM_8_FINANCIAL_STATEMENTS",
    "ITEM_1A_RISK_FACTORS",
    "ITEM_7_MDA",
    "ITEM_2_MDA",
}


def extract_policy_disclosures(section, session) -> list[PolicyDisclosure]:
    if section.section_code not in POLICY_SECTIONS:
        return []

    disclosures: list[PolicyDisclosure] = []
    text = section.section_text
    now = utcnow()

    for policy_type, pattern, window in POLICY_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            start = max(0, match.start() - 100)
            end = min(len(text), match.end() + window)
            excerpt = text[start:end].strip()
            if len(excerpt) < 50:
                continue

            disclosures.append(
                PolicyDisclosure(
                    filing_id=section.filing_id,
                    section_id=section.id,
                    policy_type=policy_type,
                    policy_text=excerpt,
                    is_new_vs_prior=None,
                    change_summary=None,
                    confidence=0.9,
                    created_at=now,
                )
            )

    return disclosures
