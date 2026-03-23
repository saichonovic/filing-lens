from __future__ import annotations

from datetime import datetime, timezone


def build_alert_payloads(report: dict) -> list[dict]:
    alerts: list[dict] = []
    for filing in report["filings"]:
        for signal in filing["signals"]:
            if signal["severity"] not in ("MEDIUM", "HIGH"):
                continue
            alerts.append(
                {
                    "alert_type": "filing_signal",
                    "ticker": report["issuer"]["ticker"],
                    "company_name": report["issuer"]["name"],
                    "form_type": filing["form_type"],
                    "period": filing.get("period_label"),
                    "filing_date": filing["filing_date"],
                    "signal_type": signal["signal_type"],
                    "signal_family": signal["signal_family"],
                    "severity": signal["severity"],
                    "verdict": signal["verdict"],
                    "score": signal["score"],
                    "headline": f"{signal['severity']} RISK: {signal['signal_type'].replace('_', ' ').title()} detected in {report['issuer']['ticker']} {filing['form_type']} {filing.get('period_label', '')}".strip(),
                    "summary": signal["summary"],
                    "investor_question": signal["investor_question"],
                    "evidence_count": signal["evidence_count"],
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                }
            )
    return alerts
