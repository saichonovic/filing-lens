from __future__ import annotations

from sqlalchemy import select

from models.tables import DetectedSignal, FilingSection, PolicyDisclosure


DOCETL_GATE = {
    "accrual_divergence": "MEDIUM",
    "channel_stuffing": "MEDIUM",
    "covenant_stress": "MEDIUM",
    "auditor_change": "LOW",
}


def should_run_docetl(signal: DetectedSignal) -> bool:
    gate = DOCETL_GATE.get(signal.signal_type)
    if not gate:
        return False
    severity_rank = {"CLEAN": 0, "LOW": 1, "WATCH": 1, "MEDIUM": 2, "HIGH": 3}
    return severity_rank.get(signal.severity, 0) >= severity_rank.get(gate, 2)


def run_policy_change_narrative(filing_id: str, prior_filing_id: str, policy_type: str, session, llm_client) -> str | None:
    current_policy = session.scalar(
        select(PolicyDisclosure).where(
            PolicyDisclosure.filing_id == filing_id,
            PolicyDisclosure.policy_type == policy_type,
            PolicyDisclosure.is_new_vs_prior.is_(True),
        )
    )
    if current_policy is None:
        return None
    prior_policy = session.scalar(
        select(PolicyDisclosure).where(
            PolicyDisclosure.filing_id == prior_filing_id,
            PolicyDisclosure.policy_type == policy_type,
        )
    )
    prior_text = prior_policy.policy_text if prior_policy else "[No equivalent policy in prior filing]"
    prompt = f"""You are analyzing SEC filing policy language changes.\n\nCURRENT FILING POLICY ({policy_type}):\n{(current_policy.policy_text or '')[:1000]}\n\nPRIOR FILING POLICY:\n{prior_text[:1000]}\n\nIn 2-3 sentences explain:\n1. What specifically changed\n2. Whether the change increases investor risk (and why)\n3. One specific question investors should ask management\n\nBe concrete. Reference actual language differences."""
    response = llm_client.messages.create(model="claude-sonnet-4-5", max_tokens=300, messages=[{"role": "user", "content": prompt}])
    narrative = response.content[0].text
    current_policy.change_summary = narrative
    session.flush()
    return narrative


def run_signal_narrative(signal: DetectedSignal, filing_id: str, prior_filing_id: str | None, session, llm_client) -> str:
    if not should_run_docetl(signal):
        return signal.summary or ""

    section_map = {
        "accrual_divergence": "ITEM_7_MDA",
        "channel_stuffing": "ITEM_7_MDA",
        "covenant_stress": "FOOTNOTE_DEBT",
    }
    section_text = ""
    section_code = section_map.get(signal.signal_type)
    if section_code:
        section = session.scalar(
            select(FilingSection)
            .where(FilingSection.filing_id == filing_id, FilingSection.section_code == section_code)
            .order_by(FilingSection.confidence.desc())
        )
        if section:
            section_text = (section.section_text or "")[:2000]

    prompt = f"""You are an SEC filing analyst reviewing a risk signal.\n\nSIGNAL TYPE: {signal.signal_type}\nSEVERITY: {signal.severity}\nDETERMINISTIC FINDINGS: {signal.summary}\n\nRELEVANT FILING TEXT:\n{section_text}\n\nIn 3-4 sentences:\n1. Confirm or qualify the deterministic finding with specific language from the filing\n2. Explain what this means for a retail investor in plain English\n3. State what to watch for in the next quarterly filing\n\nDo not invent numbers. Only reference what the filing actually says."""
    response = llm_client.messages.create(model="claude-sonnet-4-5", max_tokens=400, messages=[{"role": "user", "content": prompt}])
    enriched_summary = (signal.summary or "") + "\n\nANALYST NOTE: " + response.content[0].text
    signal.summary = enriched_summary
    signal.detection_method = "llm_supported"
    session.flush()
    return enriched_summary
