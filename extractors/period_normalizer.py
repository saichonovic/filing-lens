from __future__ import annotations

from datetime import timedelta

from models.base import utcnow
from models.tables import FilingPeriod


def normalize_periods(filing, session) -> list[FilingPeriod]:
    periods: list[FilingPeriod] = []
    now = utcnow()

    if not filing.period_end_date:
        return periods

    if filing.form_type in ("10-K", "10-K/A", "DEF 14A", "DEF14A"):
        periods.append(
            FilingPeriod(
                filing_id=filing.id,
                period_type="annual",
                start_date=_fiscal_year_start(filing.period_end_date),
                end_date=filing.period_end_date,
                period_label=f"FY{filing.fiscal_year or filing.period_end_date.year}",
                comparable_prior_filing_id=None,
                created_at=now,
            )
        )
    elif filing.form_type in ("10-Q", "10-Q/A"):
        quarter = filing.fiscal_quarter or 1
        periods.append(
            FilingPeriod(
                filing_id=filing.id,
                period_type="quarterly",
                start_date=_quarter_start(filing.period_end_date),
                end_date=filing.period_end_date,
                period_label=f"Q{quarter}-{filing.fiscal_year or filing.period_end_date.year}",
                comparable_prior_filing_id=None,
                created_at=now,
            )
        )

    return periods


def _fiscal_year_start(period_end):
    return period_end - timedelta(days=364)


def _quarter_start(period_end):
    return period_end - timedelta(days=89)
