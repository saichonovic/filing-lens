from __future__ import annotations

import difflib

from sqlalchemy import select

from models.tables import PolicyDisclosure


SIMILARITY_THRESHOLD = 0.85


def detect_policy_changes(current_filing_id: str, prior_filing_id: str, session) -> int:
    current_policies = session.scalars(
        select(PolicyDisclosure).where(PolicyDisclosure.filing_id == current_filing_id)
    ).all()
    prior_policies = session.scalars(
        select(PolicyDisclosure).where(PolicyDisclosure.filing_id == prior_filing_id)
    ).all()

    prior_by_type: dict[str, list[PolicyDisclosure]] = {}
    for prior_policy in prior_policies:
        if prior_policy.policy_type:
            prior_by_type.setdefault(prior_policy.policy_type, []).append(prior_policy)

    updated = 0
    for current_policy in current_policies:
        if not current_policy.policy_type:
            continue
        prior_matches = prior_by_type.get(current_policy.policy_type, [])
        if not prior_matches:
            current_policy.is_new_vs_prior = True
            updated += 1
            continue

        best_similarity = max(
            difflib.SequenceMatcher(
                None,
                (current_policy.policy_text or "")[:500],
                (prior_policy.policy_text or "")[:500],
            ).ratio()
            for prior_policy in prior_matches
        )
        if best_similarity >= SIMILARITY_THRESHOLD:
            current_policy.is_new_vs_prior = False
        else:
            current_policy.is_new_vs_prior = True
            current_policy.change_summary = f"__pending_llm_review__ similarity={best_similarity:.2f}"
        updated += 1

    session.flush()
    return updated
