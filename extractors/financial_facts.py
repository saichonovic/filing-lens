from __future__ import annotations


ALLOWED_PHASE1_SOURCE_METHODS = {"xbrl", "table_parse", "regex"}


def extract_financial_facts(document_text: str) -> list[dict]:
    """Extract canonical numeric facts without LLM assistance in Phase 1."""
    return []
