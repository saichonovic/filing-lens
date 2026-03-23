from __future__ import annotations

from sqlalchemy import select

from models.base import utcnow
from models.tables import DetectedSignal, FilingSection
from signals.common import replace_signal


def run_event_signals(filing_id: str, issuer_id: str, session) -> list[DetectedSignal]:
    signals: list[DetectedSignal] = []
    auditor_change = session.scalar(
        select(FilingSection).where(
            FilingSection.filing_id == filing_id,
            FilingSection.section_code == "ITEM_4_01_AUDITOR_CHANGE",
        )
    )
    if auditor_change:
        signal = DetectedSignal(
            issuer_id=issuer_id,
            filing_id=filing_id,
            signal_type="auditor_change",
            signal_family="governance_event_risk",
            severity="HIGH",
            score=9.0,
            verdict="HIGH_RISK",
            status="active",
            detection_method="deterministic",
            summary="Auditor change detected (8-K Item 4.01). This is among the strongest leading distress indicators.",
            investor_question="What were the reasons for the auditor change? Were there disagreements on accounting treatments?",
            created_at=utcnow(),
        )
        signals.append(replace_signal(signal, session))
    session.flush()
    return signals
