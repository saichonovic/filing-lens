from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from models.base import utcnow
from models.tables import Filing, FilingPeriod


def infer_fiscal_quarter(period_end_date, fiscal_year_end_month: int = 9) -> int:
    end_month = period_end_date.month
    fy_start_month = (fiscal_year_end_month % 12) + 1
    months_into_fy = ((end_month - fy_start_month) % 12) + 1
    if months_into_fy <= 3:
        return 1
    if months_into_fy <= 6:
        return 2
    if months_into_fy <= 9:
        return 3
    return 4


def get_fiscal_year_end_month(session, issuer_id) -> int:
    latest_10k = session.scalar(
        select(Filing)
        .where(Filing.issuer_id == issuer_id, Filing.form_type == "10-K")
        .order_by(Filing.period_end_date.desc(), Filing.filing_date.desc())
    )
    if latest_10k and latest_10k.period_end_date:
        return latest_10k.period_end_date.month
    return 12


def normalize_periods(filing, session) -> list[FilingPeriod]:
    periods: list[FilingPeriod] = []
    now = utcnow()

    if not filing.period_end_date:
        return periods

    fy_end_month = get_fiscal_year_end_month(session, filing.issuer_id)

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
        quarter = infer_fiscal_quarter(filing.period_end_date, fy_end_month)
        if filing.fiscal_quarter != quarter:
            filing.fiscal_quarter = quarter
            session.flush()
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
    try:
        prior_year_same_day = period_end.replace(year=period_end.year - 1)
    except ValueError:
        prior_year_same_day = period_end.replace(year=period_end.year - 1, day=28)
    return prior_year_same_day + timedelta(days=1)


def _quarter_start(period_end):
    month = period_end.month - 3
    year = period_end.year
    while month <= 0:
        month += 12
        year -= 1
    day = min(period_end.day, _days_in_month(year, month))
    return period_end.replace(year=year, month=month, day=day) + timedelta(days=1)


def _days_in_month(year: int, month: int) -> int:
    if month == 2:
        is_leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
        return 29 if is_leap else 28
    if month in {4, 6, 9, 11}:
        return 30
    return 31
