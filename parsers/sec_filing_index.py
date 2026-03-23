from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FilingIndexEntry:
    cik: str
    ticker: str
    form_type: str
    accession_number: str
    filing_date: str
    source_url: str


def fetch_filing_index(issuer: str, form_type: str, limit: int = 2) -> list[FilingIndexEntry]:
    """Placeholder for SEC index retrieval."""
    return []
