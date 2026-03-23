from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import delete, select

from extractors.derived_ratios import compute_derived_ratios
from extractors.financial_facts import ALL_RULES, extract_facts_from_section
from extractors.period_normalizer import normalize_periods
from extractors.policy_disclosures import extract_policy_disclosures
from models.tables import Filing, FilingPeriod, FilingSection, FinancialFact, PolicyDisclosure, ReviewQueue
from pipeline.common import stage_run


def run_normalize(filing_id: str) -> dict[str, Any]:
    with stage_run("normalize", "filing", filing_id) as (session, run):
        counts = _run_normalize_in_existing_session(session, filing_id, run.id)
        run.records_written = sum(counts.values())
        return {
            "run_id": str(run.id),
            "stage": run.stage_name,
            "filing_id": filing_id,
            **counts,
        }


def run_normalize_all_extracted() -> list[dict[str, Any]]:
    with stage_run("normalize", "batch", "all_extracted") as (session, run):
        filing_ids = session.scalars(
            select(Filing.id).where(Filing.ingestion_status == "extracted").order_by(Filing.filing_date.desc())
        ).all()
        results: list[dict[str, Any]] = []
        total_records = 0
        for filing_id in filing_ids:
            counts = _run_normalize_in_existing_session(session, str(filing_id), run.id)
            total_records += sum(counts.values())
            results.append({"filing_id": str(filing_id), **counts})
        run.records_written = total_records
        return results


def _run_normalize_in_existing_session(session, filing_id: str, run_id) -> dict[str, int]:
    filing = session.scalar(select(Filing).where(Filing.id == filing_id))
    if filing is None:
        raise ValueError(f"Filing {filing_id} was not found.")

    _clear_existing_normalize_outputs(session, filing_id)

    counts = {"periods": 0, "facts": 0, "policies": 0, "ratios": 0, "review": 0}

    periods = normalize_periods(filing, session)
    for period in periods:
        session.add(period)
    session.flush()
    counts["periods"] = len(periods)
    period_id = periods[0].id if periods else None

    sections = _select_primary_sections(session, filing_id)
    pending_review_items = []

    for section in sections:
        if section.section_code in ALL_RULES and period_id is not None:
            facts, review_items = extract_facts_from_section(section, period_id, session)
            for fact in facts:
                if _fact_exists(session, filing_id, period_id, fact.fact_name, fact.source_method):
                    continue
                session.add(fact)
                counts["facts"] += 1
            pending_review_items.extend(review_items)

        for policy in extract_policy_disclosures(section, session):
            if _policy_exists(session, filing_id, policy.policy_type, policy.policy_text):
                continue
            session.add(policy)
            counts["policies"] += 1

    session.flush()

    if period_id is not None:
        ratios = compute_derived_ratios(filing.id, period_id, session)
        for ratio in ratios:
            if _fact_exists(session, filing.id, period_id, ratio.fact_name, ratio.source_method):
                continue
            session.add(ratio)
            counts["ratios"] += 1

    for item in pending_review_items:
        item.source_run_id = run_id
        if _financial_review_exists(session, item.details_json):
            continue
        session.add(item)
        counts["review"] += 1

    filing.ingestion_status = "normalized"
    session.flush()
    return counts


def _select_primary_sections(session, filing_id: str) -> list[FilingSection]:
    sections = session.scalars(
        select(FilingSection).where(FilingSection.filing_id == filing_id).order_by(FilingSection.section_order)
    ).all()

    grouped: dict[str, list[FilingSection]] = defaultdict(list)
    for section in sections:
        if section.section_code:
            grouped[section.section_code].append(section)

    selected: list[FilingSection] = []
    for section_code, section_group in grouped.items():
        selected.append(max(section_group, key=lambda section: len(section.section_text or "")))
    priority = {
        "ITEM_8_FINANCIAL_STATEMENTS": 0,
        "ITEM_1_FINANCIAL_STATEMENTS": 1,
        "FOOTNOTE_DEBT": 2,
        "ITEM_7_MDA": 3,
        "ITEM_2_MDA": 4,
        "ITEM_1A_RISK_FACTORS": 5,
    }
    return sorted(selected, key=lambda section: (priority.get(section.section_code or "", 99), section.section_order or 9999))


def _clear_existing_normalize_outputs(session, filing_id: str) -> None:
    session.execute(
        delete(ReviewQueue).where(
            ReviewQueue.object_type == "financial_fact",
            ReviewQueue.details_json["filing_id"].astext == str(filing_id),
        )
    )
    session.execute(delete(FinancialFact).where(FinancialFact.filing_id == filing_id))
    session.execute(delete(PolicyDisclosure).where(PolicyDisclosure.filing_id == filing_id))
    session.execute(delete(FilingPeriod).where(FilingPeriod.filing_id == filing_id))


def _fact_exists(session, filing_id, period_id, fact_name: str, source_method: str) -> bool:
    return session.scalar(
        select(FinancialFact.id).where(
            FinancialFact.filing_id == filing_id,
            FinancialFact.period_id == period_id,
            FinancialFact.fact_name == fact_name,
            FinancialFact.source_method == source_method,
        )
    ) is not None


def _policy_exists(session, filing_id, policy_type: str | None, policy_text: str | None) -> bool:
    return session.scalar(
        select(PolicyDisclosure.id).where(
            PolicyDisclosure.filing_id == filing_id,
            PolicyDisclosure.policy_type == policy_type,
            PolicyDisclosure.policy_text == policy_text,
        )
    ) is not None


def _financial_review_exists(session, details_json: dict) -> bool:
    return session.scalar(
        select(ReviewQueue.id).where(
            ReviewQueue.object_type == "financial_fact",
            ReviewQueue.issue_type.in_(["ambiguous_extraction", "scale_uncertainty"]),
            ReviewQueue.details_json["filing_id"].astext == details_json["filing_id"],
            ReviewQueue.details_json["fact_name"].astext == details_json["fact_name"],
            ReviewQueue.details_json["section_code"].astext == details_json["section_code"],
        )
    ) is not None
