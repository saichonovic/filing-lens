from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select

from derivations.docetl_narrative import (
    gate_passes,
    run_going_concern_narrative,
    run_policy_change_narrative,
    run_signal_narrative_enrichment,
)
from models.tables import DetectedSignal, Filing, FilingPeriod, Issuer, PolicyDisclosure, SignalEvidence
from pipeline.common import stage_run
from signals.accrual_quality import run_accrual_signal
from signals.auditor_and_management_events import run_event_signals
from signals.channel_stuffing import run_channel_stuffing_signal
from signals.covenant_stress import run_covenant_stress_signal
from signals.going_concern import run_going_concern_signal


def run_derive(issuer_id: str, signal_filter: list[str] | None = None, use_docetl: bool = False) -> dict[str, Any]:
    with stage_run("derive", "issuer", issuer_id, config_snapshot={"signals": signal_filter or ["all"], "with_docetl": use_docetl}) as (session, run):
        counts = _run_derive_in_existing_session(session, issuer_id, use_docetl=use_docetl, signal_filter=signal_filter)
        run.records_written = counts["signals"]
        return {
            "run_id": str(run.id),
            "stage": run.stage_name,
            "issuer_id": issuer_id,
            **counts,
        }


def run_derive_by_ticker(ticker: str, signal_filter: list[str] | None = None, use_docetl: bool = False) -> dict[str, Any]:
    with stage_run("derive", "ticker", ticker, config_snapshot={"signals": signal_filter or ["all"], "with_docetl": use_docetl}) as (session, run):
        issuer = session.scalar(select(Issuer).where(Issuer.ticker == ticker))
        if issuer is None:
            raise ValueError(f"Issuer with ticker {ticker} not found.")
        counts = _run_derive_in_existing_session(session, str(issuer.id), use_docetl=use_docetl, signal_filter=signal_filter)
        run.records_written = counts["signals"]
        return {
            "run_id": str(run.id),
            "stage": run.stage_name,
            "issuer_id": str(issuer.id),
            "ticker": ticker,
            **counts,
        }


def _run_derive_in_existing_session(session, issuer_id: str, use_docetl: bool = False, signal_filter: list[str] | None = None) -> dict[str, int]:
    _clear_existing_derive_outputs(session, issuer_id)

    filings = session.scalars(
        select(Filing).where(Filing.issuer_id == issuer_id).order_by(Filing.period_end_date.desc(), Filing.filing_date.desc())
    ).all()

    counts = {"signals": 0, "docetl_runs": 0, "policy_narratives": 0}
    active_filter = set(signal_filter) if signal_filter else None

    for filing in filings:
        period = session.scalar(select(FilingPeriod).where(FilingPeriod.filing_id == filing.id))
        prior_id = str(period.comparable_prior_filing_id) if period and period.comparable_prior_filing_id else None
        period_id = str(period.id) if period else None
        fid = str(filing.id)

        active_signals: list[DetectedSignal] = []
        if active_filter is None or "accrual_divergence" in active_filter:
            signal = run_accrual_signal(fid, issuer_id, period_id, session)
            if signal:
                active_signals.append(signal)

        if active_filter is None or "channel_stuffing" in active_filter:
            signal = run_channel_stuffing_signal(fid, issuer_id, prior_id, session)
            if signal:
                active_signals.append(signal)

        if active_filter is None or "covenant_stress" in active_filter:
            signal = run_covenant_stress_signal(fid, issuer_id, session)
            if signal:
                active_signals.append(signal)

        if active_filter is None or "going_concern_pre_signal" in active_filter:
            signal = run_going_concern_signal(fid, issuer_id, session)
            if signal:
                active_signals.append(signal)

        if active_filter is None or "auditor_change" in active_filter:
            active_signals.extend(run_event_signals(fid, issuer_id, session))

        counts["signals"] += len(active_signals)

        if use_docetl:
            issuer = session.scalar(select(Issuer).where(Issuer.id == issuer_id))
            if issuer is None:
                raise ValueError(f"Issuer with id {issuer_id} not found.")
            for signal in active_signals:
                if not gate_passes(signal):
                    continue
                if signal.signal_type == "going_concern_pre_signal":
                    run_going_concern_narrative(signal, filing, issuer, session)
                else:
                    run_signal_narrative_enrichment(signal, filing, issuer, session)
                counts["docetl_runs"] += 1

            new_policies = session.scalars(
                select(PolicyDisclosure).where(
                    PolicyDisclosure.filing_id == fid,
                    PolicyDisclosure.is_new_vs_prior.is_(True),
                )
            ).all()
            for policy in new_policies:
                run_policy_change_narrative(policy, prior_id, filing, issuer, session)
                if policy.change_summary:
                    counts["policy_narratives"] += 1

    session.flush()
    return counts


def _clear_existing_derive_outputs(session, issuer_id: str) -> None:
    filing_ids = session.scalars(select(Filing.id).where(Filing.issuer_id == issuer_id)).all()
    signal_ids = session.scalars(select(DetectedSignal.id).where(DetectedSignal.filing_id.in_(filing_ids))).all()
    if signal_ids:
        session.execute(delete(SignalEvidence).where(SignalEvidence.signal_id.in_(signal_ids)))
    session.execute(delete(DetectedSignal).where(DetectedSignal.filing_id.in_(filing_ids)))
