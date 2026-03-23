from __future__ import annotations

import hashlib
import re
import uuid
import warnings
from pathlib import Path

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning


SECTION_PATTERNS = {
    r"item\s*1[^a-z].*business": "ITEM_1_BUSINESS",
    r"item\s*1a.*risk\s*factor": "ITEM_1A_RISK_FACTORS",
    r"item\s*1b.*unresolved.*staff": "ITEM_1B_UNRESOLVED_COMMENTS",
    r"item\s*2.*propert": "ITEM_2_PROPERTIES",
    r"item\s*3.*legal\s*proceed": "ITEM_3_LEGAL_PROCEEDINGS",
    r"item\s*7[^a].*management.*discussion": "ITEM_7_MDA",
    r"item\s*7a.*quantitative.*market": "ITEM_7A_MARKET_RISK",
    r"item\s*8.*financial\s*statement": "ITEM_8_FINANCIAL_STATEMENTS",
    r"item\s*9a.*controls.*procedure": "ITEM_9A_CONTROLS",
    r"item\s*1[^a].*financial\s*statement": "ITEM_1_FINANCIAL_STATEMENTS",
    r"item\s*2.*management.*discussion": "ITEM_2_MDA",
    r"item\s*4.*controls.*procedure": "ITEM_4_CONTROLS",
    r"item\s*1\.01": "ITEM_1_01_MATERIAL_CONTRACT",
    r"item\s*1\.02": "ITEM_1_02_CONTRACT_TERMINATED",
    r"item\s*2\.02": "ITEM_2_02_EARNINGS",
    r"item\s*4\.01": "ITEM_4_01_AUDITOR_CHANGE",
    r"item\s*5\.02": "ITEM_5_02_EXECUTIVE_DEPARTURE",
}


def _heuristic_item_code(line: str) -> str | None:
    lowered = line.lower()
    match = re.search(r"\bitem\s+(\d+)([a-z]?)(?:\.(\d{2}))?", lowered)
    if not match:
        return None

    major = match.group(1)
    suffix = (match.group(2) or "").upper()
    decimal = match.group(3)
    if decimal:
        return f"ITEM_{major}_{decimal}"
    if suffix:
        return f"ITEM_{major}{suffix}"
    return f"ITEM_{major}"


def parse_sections(html_path: str, filing_id: uuid.UUID, document_id: uuid.UUID) -> list[dict]:
    """Parse HTML filing into canonical section dictionaries."""
    html = Path(html_path).read_text(encoding="utf-8", errors="replace")
    warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
    soup = BeautifulSoup(html, "lxml")

    for tag in soup(["script", "style", "head"]):
        tag.decompose()

    full_text = soup.get_text(separator="\n")
    lines = [line.strip() for line in full_text.splitlines() if line.strip()]

    sections: list[dict] = []
    current_code: str | None = None
    current_title: str | None = None
    current_lines: list[str] = []
    current_order = 0
    current_confidence = 1.0

    def flush_section() -> None:
        nonlocal current_code, current_title, current_lines, current_order, current_confidence
        if not current_code or not current_lines:
            current_lines = []
            return

        text = "\n".join(current_lines).strip()
        if len(text) > 100:
            sections.append(
                {
                    "filing_id": filing_id,
                    "document_id": document_id,
                    "section_code": current_code,
                    "section_title": (current_title or current_code)[:256],
                    "section_order": current_order,
                    "section_text": text,
                    "section_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    "confidence": current_confidence,
                }
            )
            current_order += 1
        current_lines = []

    for line in lines:
        matched_code: str | None = None
        matched_confidence = 1.0

        for pattern, code in SECTION_PATTERNS.items():
            if re.search(pattern, line.lower()):
                matched_code = code
                matched_confidence = 0.8 if len(line) < 25 else 1.0
                break

        if matched_code is None and line.lower().startswith("item "):
            matched_code = _heuristic_item_code(line)
            matched_confidence = 0.6 if matched_code else 1.0

        if matched_code:
            flush_section()
            current_code = matched_code
            current_title = line
            current_confidence = matched_confidence
        elif current_code:
            current_lines.append(line)

    flush_section()
    return sections
