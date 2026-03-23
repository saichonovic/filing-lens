from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select

from models.base import utcnow
from models.tables import FinancialFact


def compute_derived_ratios(filing_id, period_id, session) -> list[FinancialFact]:
    def get_fact(name: str):
        row = session.scalar(
            select(FinancialFact)
            .where(
                FinancialFact.filing_id == filing_id,
                FinancialFact.fact_name == name,
                FinancialFact.source_method == "regex",
            )
            .order_by(FinancialFact.confidence.desc(), FinancialFact.created_at.desc())
        )
        return row.fact_value_numeric if row else None

    ratios: list[FinancialFact] = []
    now = utcnow()

    def add_ratio(name: str, value):
        if value is None:
            return
        ratios.append(
            FinancialFact(
                filing_id=filing_id,
                period_id=period_id,
                fact_name=name,
                fact_category="ratio",
                fact_value_numeric=value,
                unit="ratio",
                scale="units",
                statement_type="ratio",
                source_method="derived",
                confidence=1.0,
                created_at=now,
            )
        )

    net_income = get_fact("net_income")
    operating_cf = get_fact("operating_cash_flow")
    total_assets = get_fact("total_assets")
    accounts_receivable = get_fact("accounts_receivable")
    revenue = get_fact("revenue")
    inventory = get_fact("inventory")
    capex = get_fact("capex")
    total_debt = get_fact("total_debt")
    total_equity = get_fact("total_equity")
    gross_profit = get_fact("gross_profit")

    if all(v is not None for v in [net_income, operating_cf, total_assets]) and total_assets > 0:
        add_ratio("accrual_ratio", (net_income - operating_cf) / total_assets)

    if accounts_receivable is not None and revenue is not None and revenue > 0:
        add_ratio("dso", (accounts_receivable / revenue) * Decimal("90"))

    if inventory is not None and revenue is not None and revenue > 0:
        add_ratio("inventory_to_revenue_pct", (inventory / revenue) * Decimal("100"))

    if capex is not None and revenue is not None and revenue > 0:
        add_ratio("capex_to_revenue_pct", (capex / revenue) * Decimal("100"))

    if total_debt is not None and total_equity not in (None, 0):
        add_ratio("debt_to_equity", total_debt / total_equity)

    if gross_profit is not None and revenue is not None and revenue > 0:
        add_ratio("gross_margin_pct", (gross_profit / revenue) * Decimal("100"))

    return ratios
