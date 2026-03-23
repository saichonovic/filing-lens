from __future__ import annotations


def build_investor_summary(issuer_id: str) -> dict:
    """Build a product-facing summary from canonical and derived layers."""
    return {"issuer_id": issuer_id, "summary": None}
