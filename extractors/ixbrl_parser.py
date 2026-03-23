from __future__ import annotations

from decimal import Decimal, InvalidOperation
import warnings

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

from models.base import utcnow
from models.tables import FinancialFact

from extractors.xbrl_facts import XBRL_CONCEPT_MAP, _category_for, _normalize_to_millions


def extract_ixbrl_facts(html_path: str, filing_id, period_id, committed_names: set[str]) -> list[FinancialFact]:
    html = open(html_path, "r", encoding="utf-8", errors="replace").read()
    warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
    soup = BeautifulSoup(html, "lxml")

    ix_tags = soup.find_all(lambda tag: tag.name and tag.name.lower().endswith("nonfraction"))
    if not ix_tags:
        ix_tags = soup.find_all(attrs={"name": True, "contextref": True})

    facts: list[FinancialFact] = []
    for tag in ix_tags:
        concept = tag.get("name", "")
        if not concept.startswith("us-gaap:"):
            continue
        fact_name = XBRL_CONCEPT_MAP.get(concept)
        if not fact_name or fact_name in committed_names:
            continue

        raw_text = tag.get_text(strip=True).replace(",", "")
        if not raw_text:
            continue
        try:
            value = Decimal(raw_text.replace("(", "").replace(")", ""))
        except InvalidOperation:
            continue
        if tag.get("sign") == "-" or "(" in tag.get_text():
            value = -abs(value)

        unit_ref = str(tag.get("unitref", "USD")).upper()
        unit = "USD" if "USD" in unit_ref else unit_ref
        value, scale = _normalize_to_millions(value, unit, fact_name)
        facts.append(
            FinancialFact(
                filing_id=filing_id,
                period_id=period_id,
                fact_name=fact_name,
                fact_category=_category_for(fact_name),
                fact_value_numeric=value,
                unit=unit,
                scale=scale,
                statement_type=_category_for(fact_name),
                source_method="ixbrl",
                confidence=0.95,
                created_at=utcnow(),
            )
        )
        committed_names.add(fact_name)

    return facts
