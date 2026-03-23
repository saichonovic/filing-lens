from __future__ import annotations

from rich import box
from rich.console import Console
from rich.table import Table


console = Console()

VERDICT_STYLE = {
    "CLEAN": "bold green",
    "WATCH": "bold yellow",
    "CAUTION": "bold dark_orange",
    "HIGH_RISK": "bold red",
}

SEVERITY_ICON = {
    "CLEAN": "[OK]",
    "LOW": "[!]",
    "WATCH": "[!]",
    "MEDIUM": "[!]",
    "HIGH": "[!]",
}


def print_issuer_report(report: dict) -> None:
    issuer = report["issuer"]
    console.print()
    console.print(f"[bold]FilingLens - {issuer['ticker']} | {issuer['name']}[/bold]")
    console.print("=" * 72)
    console.print()

    for filing in report["filings"]:
        verdict = filing["overall_verdict"]
        verdict_style = VERDICT_STYLE.get(verdict, "white")
        period = filing.get("period_label") or filing["form_type"]
        console.print(
            f"[bold]{filing['form_type']}[/bold]  {period}  Filed: {filing['filing_date'][:10]}  Overall: [{verdict_style}]{verdict}[/{verdict_style}]"
        )

        facts = filing["facts"]
        if any(value is not None for value in facts.values()):
            table = Table(box=box.SIMPLE, show_header=True, header_style="bold cyan", padding=(0, 1))
            table.add_column("Metric")
            table.add_column("Value", justify="right")
            table.add_row("Revenue", _fmt_currency(facts["revenue"]))
            table.add_row("Net Income", _fmt_currency(facts["net_income"]))
            table.add_row("Operating Cash Flow", _fmt_currency(facts["operating_cash_flow"]))
            table.add_row("Accrual Ratio", _fmt_ratio(facts["accrual_ratio"]))
            table.add_row("DSO (days)", _fmt_number(facts["dso"]))
            table.add_row("Gross Margin", _fmt_percent(facts["gross_margin_pct"]))
            console.print(table)

        comparison = filing.get("comparison")
        if comparison and comparison["flags"]:
            console.print("  [bold cyan]YoY Material Changes[/bold cyan]")
            for flag in comparison["flags"]:
                arrow = "UP" if flag["direction"] == "up" else "DOWN"
                color = "green" if flag["direction"] == "up" and flag["fact"] in {"revenue", "net_income", "operating_cash_flow", "gross_margin_pct"} else "red"
                console.print(
                    f"  [{color}]{arrow}[/{color}] {flag['fact']}: {flag['change_pct']:+.1f}%  ({flag['prior']:,.0f} -> {flag['current']:,.0f})"
                )
            console.print()

        if filing["signals"]:
            console.print("  [bold]Risk Signals[/bold]")
            for signal in filing["signals"]:
                icon = SEVERITY_ICON.get(signal["severity"], "[ ]")
                style = VERDICT_STYLE.get({"MEDIUM": "CAUTION", "HIGH": "HIGH_RISK", "LOW": "WATCH"}.get(signal["severity"], signal["severity"]), "white")
                console.print(
                    f"  {icon} [{style}]{signal['severity']}[/{style}]  [bold]{signal['signal_type']}[/bold]  score={signal['score']:.1f}  method={signal['detection_method']}"
                )
                console.print(f"     {signal['summary']}")
                if signal["investor_question"]:
                    console.print(f"     [dim]Q: {signal['investor_question']}[/dim]")
                console.print()
        else:
            console.print("  [green]No signals detected - clean filing[/green]\n")

        if filing["policy_disclosures"]:
            for policy in filing["policy_disclosures"]:
                new_tag = " [yellow][NEW][/yellow]" if policy["is_new_vs_prior"] else ""
                console.print(f"   Policy: [bold]{policy['policy_type']}[/bold]{new_tag}")
                if policy["change_summary"] and not str(policy["change_summary"]).startswith("__pending"):
                    console.print(f"     {policy['change_summary']}")
                else:
                    console.print(f"     [dim]{policy['text_preview']}...[/dim]")
                console.print()

        console.print("-" * 72)


def _fmt_currency(value):
    if value is None:
        return "-"
    return f"${value:,.0f}M"


def _fmt_percent(value):
    if value is None:
        return "-"
    return f"{value:.1f}%"


def _fmt_ratio(value):
    if value is None:
        return "-"
    return f"{value:.4f}"


def _fmt_number(value):
    if value is None:
        return "-"
    return f"{value:.1f}"
