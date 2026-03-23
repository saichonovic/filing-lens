from __future__ import annotations

from typing import Any

from derivations.alert_builder import build_alert_payloads
from derivations.cli_printer import console, print_issuer_report
from derivations.json_exporter import export_issuer_json
from derivations.report_builder import build_issuer_report
from models.tables import Issuer
from pipeline.common import stage_run


def run_publish(issuer_id: str, output_json: bool = True, print_report: bool = True, print_alerts: bool = True) -> dict[str, Any]:
    with stage_run("publish", "issuer", issuer_id, config_snapshot={"output_json": output_json, "print_report": print_report, "print_alerts": print_alerts}) as (session, run):
        report = build_issuer_report(issuer_id, session)
        if print_report:
            print_issuer_report(report)

        export_path = export_issuer_json(report) if output_json else None
        alerts = build_alert_payloads(report)
        if print_alerts and alerts:
            console.print("\n[bold red]ALERTS[/bold red]")
            for alert in alerts:
                console.print(f"\n[bold]{alert['headline']}[/bold]\n{alert['summary']}")
                if alert["investor_question"]:
                    console.print(f"[dim]? {alert['investor_question']}[/dim]")

        run.records_written = len(alerts)
        return {
            "signals_reported": sum(len(filing["signals"]) for filing in report["filings"]),
            "alerts_generated": len(alerts),
            "export_path": str(export_path) if export_path else None,
            "overall_verdicts": {filing["period_label"]: filing["overall_verdict"] for filing in report["filings"]},
        }


def run_publish_by_ticker(ticker: str, output_json: bool = True, print_report: bool = True, print_alerts: bool = True) -> dict[str, Any]:
    with stage_run("publish", "ticker", ticker, config_snapshot={"output_json": output_json, "print_report": print_report, "print_alerts": print_alerts}) as (session, run):
        issuer = session.query(Issuer).filter_by(ticker=ticker).first()
        if issuer is None:
            raise ValueError(f"Issuer with ticker {ticker} not found.")
        report = build_issuer_report(str(issuer.id), session)
        if print_report:
            print_issuer_report(report)

        export_path = export_issuer_json(report) if output_json else None
        alerts = build_alert_payloads(report)
        if print_alerts and alerts:
            console.print("\n[bold red]ALERTS[/bold red]")
            for alert in alerts:
                console.print(f"\n[bold]{alert['headline']}[/bold]\n{alert['summary']}")
                if alert["investor_question"]:
                    console.print(f"[dim]? {alert['investor_question']}[/dim]")

        run.records_written = len(alerts)
        return {
            "signals_reported": sum(len(filing["signals"]) for filing in report["filings"]),
            "alerts_generated": len(alerts),
            "export_path": str(export_path) if export_path else None,
            "overall_verdicts": {filing["period_label"]: filing["overall_verdict"] for filing in report["filings"]},
        }
