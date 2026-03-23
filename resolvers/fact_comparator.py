from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select

from models.base import utcnow
from models.tables import FilingComparison, FinancialFact


COMPARABLE_FACTS = [
    "revenue",
    "gross_profit",
    "operating_income",
    "net_income",
    "operating_cash_flow",
    "capex",
    "accounts_receivable",
    "inventory",
    "total_debt",
    "total_equity",
    "total_assets",
    "diluted_eps",
    "accrual_ratio",
    "dso",
    "inventory_to_revenue_pct",
    "capex_to_revenue_pct",
    "gross_margin_pct",
    "debt_to_equity",
]

MATERIALITY = {
    "accrual_ratio": Decimal("0.02"),
    "gross_margin_pct": Decimal("2.0"),
    "capex_to_revenue_pct": Decimal("2.0"),
    "dso": Decimal("5.0"),
    "inventory_to_revenue_pct": Decimal("3.0"),
    "debt_to_equity": Decimal("0.2"),
}
DEFAULT_MATERIALITY_PCT = Decimal("2.0")


def build_fact_comparison(current_filing_id: str, prior_filing_id: str, session) -> FilingComparison:
    current_facts = _get_facts(current_filing_id, session)
    prior_facts = _get_facts(prior_filing_id, session)

    diffs: dict[str, dict] = {}
    flags: list[dict] = []

    for fact_name in COMPARABLE_FACTS:
        curr = current_facts.get(fact_name)
        prev = prior_facts.get(fact_name)
        if not curr or not prev:
            continue

        curr_val = curr["value"]
        prev_val = prev["value"]
        if prev_val in (None, 0):
            continue

        abs_change = curr_val - prev_val
        pct_change = (abs_change / abs(prev_val)) * Decimal("100")
        threshold = MATERIALITY.get(fact_name)
        if threshold is not None:
            is_material = abs(abs_change) >= threshold
        else:
            is_material = abs(pct_change) >= DEFAULT_MATERIALITY_PCT

        diffs[fact_name] = {
            "current": float(curr_val),
            "prior": float(prev_val),
            "abs_change": float(abs_change),
            "pct_change": round(float(pct_change), 2),
            "unit": curr["unit"],
            "material": is_material,
            "direction": "up" if abs_change > 0 else "down",
        }
        if is_material:
            flags.append(
                {
                    "fact": fact_name,
                    "change_pct": round(float(pct_change), 2),
                    "direction": "up" if abs_change > 0 else "down",
                    "current": float(curr_val),
                    "prior": float(prev_val),
                }
            )

    comparison_type = "yoy_annual"
    return FilingComparison(
        current_filing_id=current_filing_id,
        comparison_filing_id=prior_filing_id,
        comparison_type=comparison_type,
        summary_json={
            "fact_pairs_compared": len(diffs),
            "material_changes": len(flags),
            "flags": flags,
            "diffs": diffs,
        },
        created_at=utcnow(),
    )


def _get_facts(filing_id: str, session) -> dict[str, dict]:
    rows = session.scalars(
        select(FinancialFact)
        .where(
            FinancialFact.filing_id == filing_id,
            FinancialFact.fact_name.in_(COMPARABLE_FACTS),
            FinancialFact.confidence >= 0.75,
        )
        .order_by(FinancialFact.fact_name, FinancialFact.confidence.desc(), FinancialFact.created_at.desc())
    ).all()

    result: dict[str, dict] = {}
    for row in rows:
        if row.fact_name not in result:
            result[row.fact_name] = {
                "value": row.fact_value_numeric,
                "confidence": row.confidence,
                "unit": row.unit,
            }
    return result
