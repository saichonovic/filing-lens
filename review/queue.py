from __future__ import annotations


def enqueue_review(object_type: str, issue_type: str, details: dict | None = None) -> dict:
    """Placeholder helper for writing ambiguity cases to the review queue."""
    return {"object_type": object_type, "issue_type": issue_type, "details": details or {}}
