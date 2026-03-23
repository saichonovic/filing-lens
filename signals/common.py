from __future__ import annotations

from sqlalchemy import select

from models.tables import DetectedSignal, SignalEvidence


def replace_signal(signal: DetectedSignal, session) -> DetectedSignal:
    existing = session.scalar(
        select(DetectedSignal).where(
            DetectedSignal.issuer_id == signal.issuer_id,
            DetectedSignal.filing_id == signal.filing_id,
            DetectedSignal.signal_type == signal.signal_type,
        )
    )
    if existing is not None:
        session.query(SignalEvidence).filter(SignalEvidence.signal_id == existing.id).delete()
        session.delete(existing)
        session.flush()
    session.add(signal)
    session.flush()
    return signal
