from __future__ import annotations

from pipeline.common import stage_run


def run_resolve(issuer_id: str) -> dict:
    """Align filings across periods. Ambiguous cases route to review."""
    with stage_run("resolve", "issuer", issuer_id) as (_, run):
        return {
            "run_id": str(run.id),
            "stage": run.stage_name,
            "issuer_id": issuer_id,
            "message": "Resolve stage scaffolded. Prior-filing matching and review routing not yet implemented.",
        }
