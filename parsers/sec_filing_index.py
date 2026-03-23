from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests

from app.config import settings


SEC_BASE = "https://data.sec.gov"
ARCHIVES_BASE = "https://www.sec.gov/Archives"
TICKER_LOOKUP_URL = "https://www.sec.gov/files/company_tickers.json"


@dataclass
class FilingIndexEntry:
    cik: str
    company_name: str
    ticker: str
    form_type: str
    accession_number: str
    filing_date: datetime
    period_end_date: str | None
    primary_document: str | None
    source_url: str
    source_format: str | None
    amendment_flag: bool


def _headers() -> dict[str, str]:
    return {
        "User-Agent": settings.sec_user_agent,
        "Accept-Encoding": "gzip, deflate",
    }


def _get_json(url: str) -> Any:
    response = requests.get(url, headers=_headers(), timeout=30)
    response.raise_for_status()
    return response.json()


def _normalize_cik(cik_value: str | int) -> str:
    return str(cik_value).strip().lstrip("0") or "0"


def _padded_cik(cik_value: str | int) -> str:
    return _normalize_cik(cik_value).zfill(10)


def _resolve_company(issuer: str) -> dict[str, Any]:
    lookup = _get_json(TICKER_LOOKUP_URL)
    issuer_upper = issuer.strip().upper()
    issuer_lower = issuer.strip().lower()

    matches: list[dict[str, Any]] = []
    for row in lookup.values():
        ticker = str(row.get("ticker", "")).upper()
        title = str(row.get("title", ""))
        cik_str = _normalize_cik(row.get("cik_str", ""))
        if issuer_upper == ticker or issuer == cik_str or issuer_lower == title.lower():
            matches.append(row)

    if not matches:
        for row in lookup.values():
            title = str(row.get("title", ""))
            ticker = str(row.get("ticker", "")).upper()
            if issuer_lower in title.lower() or issuer_upper == ticker:
                matches.append(row)

    if not matches:
        raise ValueError(f"No SEC company match found for issuer '{issuer}'.")

    matches.sort(key=lambda row: (str(row.get("ticker", "")).upper() != issuer_upper, len(str(row.get("title", "")))))
    return matches[0]


def _parse_filing_date(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def _primary_document_url(cik: str, accession_number: str, primary_document: str | None) -> str:
    if not primary_document:
        return f"{ARCHIVES_BASE}/edgar/data/{int(cik)}/{accession_number.replace('-', '')}/"
    return f"{ARCHIVES_BASE}/edgar/data/{int(cik)}/{accession_number.replace('-', '')}/{primary_document}"


def _guess_source_format(primary_document: str | None) -> str | None:
    if not primary_document or "." not in primary_document:
        return None
    return primary_document.rsplit(".", 1)[-1].lower()


def fetch_filing_index(issuer: str, form_type: str, limit: int = 2) -> list[FilingIndexEntry]:
    """Resolve an issuer against SEC data and return recent filing metadata."""
    company = _resolve_company(issuer)
    cik = _normalize_cik(company["cik_str"])
    submissions = _get_json(f"{SEC_BASE}/submissions/CIK{_padded_cik(cik)}.json")
    recent = submissions.get("filings", {}).get("recent", {})

    forms = recent.get("form", [])
    accession_numbers = recent.get("accessionNumber", [])
    filing_dates = recent.get("filingDate", [])
    report_dates = recent.get("reportDate", [])
    primary_documents = recent.get("primaryDocument", [])

    wanted_form = form_type.strip().upper()
    entries: list[FilingIndexEntry] = []
    for index, current_form in enumerate(forms):
        current_form_upper = str(current_form).upper()
        if wanted_form != "ALL" and current_form_upper != wanted_form:
            continue

        accession_number = accession_numbers[index]
        primary_document = primary_documents[index] if index < len(primary_documents) else None
        filing_date = filing_dates[index]
        period_end_date = report_dates[index] if index < len(report_dates) else None
        entries.append(
            FilingIndexEntry(
                cik=cik,
                company_name=str(company["title"]),
                ticker=str(company["ticker"]).upper(),
                form_type=current_form_upper,
                accession_number=accession_number,
                filing_date=_parse_filing_date(filing_date),
                period_end_date=period_end_date or None,
                primary_document=primary_document or None,
                source_url=_primary_document_url(cik, accession_number, primary_document),
                source_format=_guess_source_format(primary_document),
                amendment_flag="/A" in current_form_upper,
            )
        )
        if len(entries) >= limit:
            break

    return entries
