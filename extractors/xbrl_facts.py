from __future__ import annotations

import json
import time
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

import requests

from app.config import settings
from models.base import utcnow
from models.tables import FinancialFact


XBRL_CONCEPT_MAP = {
    "us-gaap:Revenues": "revenue",
    "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax": "revenue",
    "us-gaap:SalesRevenueNet": "revenue",
    "us-gaap:SalesRevenueGoodsNet": "revenue",
    "us-gaap:RevenueFromContractWithCustomerIncludingAssessedTax": "revenue",
    "us-gaap:NetIncomeLoss": "net_income",
    "us-gaap:NetIncomeLossAvailableToCommonStockholdersBasic": "net_income",
    "us-gaap:GrossProfit": "gross_profit",
    "us-gaap:OperatingIncomeLoss": "operating_income",
    "us-gaap:EarningsPerShareDiluted": "diluted_eps",
    "us-gaap:EarningsPerShareBasic": "basic_eps",
    "us-gaap:CashAndCashEquivalentsAtCarryingValue": "cash_and_equivalents",
    "us-gaap:CashCashEquivalentsAndShortTermInvestments": "cash_and_equivalents",
    "us-gaap:AccountsReceivableNetCurrent": "accounts_receivable",
    "us-gaap:InventoryNet": "inventory",
    "us-gaap:Assets": "total_assets",
    "us-gaap:LongTermDebtNoncurrent": "total_debt",
    "us-gaap:LongTermDebt": "total_debt",
    "us-gaap:DebtCurrent": "short_term_debt",
    "us-gaap:StockholdersEquity": "total_equity",
    "us-gaap:StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest": "total_equity",
    "us-gaap:NetCashProvidedByUsedInOperatingActivities": "operating_cash_flow",
    "us-gaap:NetCashProvidedByUsedInOperatingActivitiesContinuingOperations": "operating_cash_flow",
    "us-gaap:PaymentsToAcquirePropertyPlantAndEquipment": "capex",
    "us-gaap:CapitalExpendituresIncurredButNotYetPaid": "capex",
    "us-gaap:NetCashProvidedByUsedInFinancingActivities": "financing_cash_flow",
    "us-gaap:NetCashProvidedByUsedInInvestingActivities": "investing_cash_flow",
}

CONCEPT_PRIORITY = {
    "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax": 0,
    "us-gaap:RevenueFromContractWithCustomerIncludingAssessedTax": 1,
    "us-gaap:Revenues": 2,
    "us-gaap:SalesRevenueNet": 3,
    "us-gaap:SalesRevenueGoodsNet": 4,
    "us-gaap:NetIncomeLoss": 0,
    "us-gaap:NetIncomeLossAvailableToCommonStockholdersBasic": 1,
    "us-gaap:NetCashProvidedByUsedInOperatingActivities": 0,
    "us-gaap:NetCashProvidedByUsedInOperatingActivitiesContinuingOperations": 1,
    "us-gaap:CashAndCashEquivalentsAtCarryingValue": 0,
    "us-gaap:CashCashEquivalentsAndShortTermInvestments": 1,
    "us-gaap:LongTermDebtNoncurrent": 0,
    "us-gaap:LongTermDebt": 1,
}

INVERT_FOR_STORAGE = {
    "us-gaap:PaymentsToAcquirePropertyPlantAndEquipment",
}

COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"


def fetch_companyfacts(cik: str) -> dict | None:
    cik_padded = str(cik).lstrip("0").zfill(10)
    cache_path = Path("storage/xbrl") / f"{cik_padded}_companyfacts.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    if cache_path.exists():
        age_hours = (time.time() - cache_path.stat().st_mtime) / 3600
        if age_hours < 24:
            return json.loads(cache_path.read_text(encoding="utf-8"))

    try:
        response = requests.get(
            COMPANYFACTS_URL.format(cik=cik_padded),
            headers={"User-Agent": settings.sec_user_agent},
            timeout=30,
        )
        response.raise_for_status()
    except Exception:
        return None

    cache_path.write_text(response.text, encoding="utf-8")
    time.sleep(0.1)
    return response.json()


def extract_facts_from_companyfacts(
    companyfacts: dict,
    filing_accession: str,
    period_end_date: date,
    filing_id,
    period_id,
    form_type: str,
) -> tuple[list[FinancialFact], list]:
    best_by_fact: dict[str, tuple[tuple, FinancialFact]] = {}
    accession_clean = filing_accession.replace("-", "")
    gaap = companyfacts.get("facts", {}).get("us-gaap", {})
    if not gaap:
        return [], []

    is_annual = form_type in ("10-K", "10-K/A")
    is_quarterly = form_type in ("10-Q", "10-Q/A")

    for xbrl_concept, fact_name in XBRL_CONCEPT_MAP.items():
        concept_key = xbrl_concept.replace("us-gaap:", "")
        concept_data = gaap.get(concept_key)
        if not concept_data:
            continue

        unit_key, unit_facts = _pick_unit_facts(concept_data.get("units", {}))
        if unit_key is None:
            continue

        best = _find_best_fact(unit_facts, accession_clean, period_end_date, is_annual, is_quarterly)
        if not best:
            continue

        try:
            value = Decimal(str(best["val"]))
        except (InvalidOperation, KeyError):
            continue

        if xbrl_concept in INVERT_FOR_STORAGE:
            value = -abs(value)

        unit = "USD" if unit_key.upper() == "USD" else unit_key
        value, scale = _normalize_to_millions(value, unit, fact_name)
        fact = FinancialFact(
            filing_id=filing_id,
            period_id=period_id,
            fact_name=fact_name,
            fact_category=_category_for(fact_name),
            fact_value_numeric=value,
            unit=unit,
            scale=scale,
            statement_type=_category_for(fact_name),
            source_method="xbrl",
            confidence=1.0,
            created_at=utcnow(),
        )
        rank = _entry_rank(best, period_end_date, is_annual, is_quarterly)
        priority = CONCEPT_PRIORITY.get(xbrl_concept, 99)
        candidate_score = (rank, priority)
        current = best_by_fact.get(fact_name)
        if current is None or candidate_score < current[0]:
            best_by_fact[fact_name] = (candidate_score, fact)

    return [value[1] for value in best_by_fact.values()], []


def _pick_unit_facts(units_data: dict) -> tuple[str | None, list]:
    if "USD" in units_data:
        return "USD", units_data["USD"]
    if "shares" in units_data:
        return "shares", units_data["shares"]
    for key, value in units_data.items():
        return key, value
    return None, []


def _find_best_fact(unit_facts: list, accession_clean: str, period_end: date, is_annual: bool, is_quarterly: bool) -> dict | None:
    exact_matches = [entry for entry in unit_facts if entry.get("accn", "").replace("-", "") == accession_clean]
    if exact_matches:
        end_matches = [entry for entry in exact_matches if _end_distance(entry, period_end) <= 5]
        if end_matches:
            return _rank_candidates(end_matches, period_end, is_annual, is_quarterly)
        return _rank_candidates(exact_matches, period_end, is_annual, is_quarterly)

    candidates = []
    for entry in unit_facts:
        try:
            entry_end = date.fromisoformat(entry.get("end", ""))
        except ValueError:
            continue
        if abs((entry_end - period_end).days) <= 5:
            candidates.append(entry)
    if not candidates:
        return None
    return _rank_candidates(candidates, period_end, is_annual, is_quarterly)


def _rank_candidates(candidates: list[dict], period_end: date, is_annual: bool, is_quarterly: bool) -> dict | None:
    def duration_days(entry: dict) -> int:
        start = entry.get("start")
        end = entry.get("end")
        if not start or not end:
            return 0
        try:
            return (date.fromisoformat(end) - date.fromisoformat(start)).days
        except ValueError:
            return 0

    target = 365 if is_annual else 90 if is_quarterly else 0
    ranked = sorted(
        candidates,
        key=lambda entry: _entry_rank(entry, period_end, is_annual, is_quarterly),
    )
    return ranked[0] if ranked else None


def _entry_rank(entry: dict, period_end: date, is_annual: bool, is_quarterly: bool) -> tuple:
    target = 365 if is_annual else 90 if is_quarterly else 0
    duration = _duration_days(entry)
    frame_value = str(entry.get("frame", ""))
    if is_quarterly:
        frame_score = 0 if frame_value.endswith("Q1") or frame_value.endswith("Q2") or frame_value.endswith("Q3") or frame_value.endswith("Q4") else 1
    elif is_annual:
        frame_score = 0 if frame_value and "Q" not in frame_value else 1
    else:
        frame_score = 1
    return (
        _end_distance(entry, period_end),
        abs(duration - target) if target else duration,
        frame_score,
        abs(int(entry.get("fy", 0) or 0) - period_end.year),
    )


def _duration_days(entry: dict) -> int:
    start = entry.get("start")
    end = entry.get("end")
    if not start or not end:
        return 0
    try:
        return (date.fromisoformat(end) - date.fromisoformat(start)).days
    except ValueError:
        return 0


def _end_distance(entry: dict, period_end: date) -> int:
    try:
        return abs((date.fromisoformat(entry.get("end", "")) - period_end).days)
    except ValueError:
        return 10_000


def _normalize_to_millions(value: Decimal, unit: str, fact_name: str) -> tuple[Decimal, str]:
    if unit != "USD":
        return value, "units"
    if fact_name in {"diluted_eps", "basic_eps"}:
        return value, "units"
    return value / Decimal("1000000"), "millions"


def _category_for(fact_name: str) -> str:
    categories = {
        "revenue": "income_stmt",
        "gross_profit": "income_stmt",
        "operating_income": "income_stmt",
        "net_income": "income_stmt",
        "diluted_eps": "income_stmt",
        "basic_eps": "income_stmt",
        "cash_and_equivalents": "balance_sheet",
        "accounts_receivable": "balance_sheet",
        "inventory": "balance_sheet",
        "total_assets": "balance_sheet",
        "total_debt": "balance_sheet",
        "short_term_debt": "balance_sheet",
        "total_equity": "balance_sheet",
        "operating_cash_flow": "cash_flow",
        "capex": "cash_flow",
        "financing_cash_flow": "cash_flow",
        "investing_cash_flow": "cash_flow",
    }
    return categories.get(fact_name, "other")
