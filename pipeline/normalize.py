from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import delete, select

from extractors.derived_ratios import compute_derived_ratios
from extractors.financial_facts import ALL_RULES, DEBT_FOOTNOTE_RULES, extract_facts_from_section
from extractors.ixbrl_parser import extract_ixbrl_facts
from extractors.period_normalizer import normalize_periods
from extractors.policy_disclosures import extract_policy_disclosures
from extractors.xbrl_facts import extract_facts_from_companyfacts, fetch_companyfacts
from models.tables import DetectedSignal, Filing, FilingComparison, FilingDocument, FilingPeriod, FilingSection, FinancialFact, Issuer, PolicyDisclosure, ReviewQueue, SignalEvidence
from pipeline.common import stage_run


def run_normalize(filing_id: str, force: bool = False) -> dict[str, Any]:
    with stage_run("normalize", "filing", filing_id, config_snapshot={"force": force}) as (session, run):
        counts = _run_normalize_in_existing_session(session, filing_id, run.id)
        run.records_written = sum(counts.values())
        return {
            "run_id": str(run.id),
            "stage": run.stage_name,
            "filing_id": filing_id,
            **counts,
        }


def run_normalize_all_extracted(force: bool = False) -> list[dict[str, Any]]:
    with stage_run("normalize", "batch", "all_extracted", config_snapshot={"force": force}) as (session, run):
        filing_ids = session.scalars(
            select(Filing.id).where(Filing.ingestion_status.in_(["extracted", "normalized", "resolved", "derived"])).order_by(Filing.filing_date.desc())
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

    if period_id is not None and periods:
        facts, review_items = _extract_facts_for_filing(session, filing, periods[0], sections)
        for fact in facts:
            if _fact_exists_any_source(session, filing_id, period_id, fact.fact_name):
                continue
            session.add(fact)
            counts["facts"] += 1
        session.flush()
        pending_review_items.extend(review_items)

    for section in sections:
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


def _extract_facts_for_filing(session, filing: Filing, period: FilingPeriod, sections: list[FilingSection]) -> tuple[list[FinancialFact], list[ReviewQueue]]:
    all_facts: list[FinancialFact] = []
    all_reviews: list[ReviewQueue] = []
    committed: set[str] = set()

    issuer = session.scalar(select(Issuer).where(Issuer.id == filing.issuer_id))
    if issuer and issuer.cik:
        companyfacts = fetch_companyfacts(issuer.cik)
        if companyfacts:
            xbrl_facts, xbrl_reviews = extract_facts_from_companyfacts(
                companyfacts=companyfacts,
                filing_accession=filing.accession_number,
                period_end_date=filing.period_end_date,
                filing_id=filing.id,
                period_id=period.id,
                form_type=filing.form_type,
            )
            all_facts.extend(xbrl_facts)
            all_reviews.extend(xbrl_reviews)
            committed.update(fact.fact_name for fact in xbrl_facts)

    primary_doc = session.scalar(
        select(FilingDocument).where(
            FilingDocument.filing_id == filing.id,
            FilingDocument.document_role == "primary",
        )
    )
    if primary_doc and primary_doc.file_path:
        ixbrl_facts = extract_ixbrl_facts(
            html_path=primary_doc.file_path,
            filing_id=filing.id,
            period_id=period.id,
            committed_names=committed,
        )
        all_facts.extend(ixbrl_facts)
        committed.update(fact.fact_name for fact in ixbrl_facts)

    for section in sections:
        if section.section_code != "FOOTNOTE_DEBT":
            continue
        debt_facts, debt_reviews = extract_facts_from_section(
            section=section,
            period_id=period.id,
            session=session,
            rules_override=DEBT_FOOTNOTE_RULES,
        )
        for fact in debt_facts:
            if fact.fact_name in committed:
                continue
            all_facts.append(fact)
            committed.add(fact.fact_name)
        all_reviews.extend(debt_reviews)

    return all_facts, all_reviews


def _clear_existing_normalize_outputs(session, filing_id: str) -> None:
    signal_ids = session.scalars(select(DetectedSignal.id).where(DetectedSignal.filing_id == filing_id)).all()
    if signal_ids:
        session.execute(delete(SignalEvidence).where(SignalEvidence.signal_id.in_(signal_ids)))
    session.execute(delete(DetectedSignal).where(DetectedSignal.filing_id == filing_id))
    session.execute(
        delete(FilingComparison).where(
            FilingComparison.current_filing_id == filing_id
        )
    )
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


def _fact_exists_any_source(session, filing_id, period_id, fact_name: str) -> bool:
    return session.scalar(
        select(FinancialFact.id).where(
            FinancialFact.filing_id == filing_id,
            FinancialFact.period_id == period_id,
            FinancialFact.fact_name == fact_name,
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
