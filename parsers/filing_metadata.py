from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FilingMetadata:
    accession_number: str
    form_type: str
    filing_date: str
    period_end_date: str | None
    amendment_flag: bool


def parse_filing_metadata(raw_text: str) -> FilingMetadata | None:
    """Placeholder for deterministic filing metadata extraction."""
    return None
