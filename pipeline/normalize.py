from __future__ import annotations

from pipeline.common import stage_run


def run_normalize(filing_id: str) -> dict:
    """Build sections, periods, facts, and policy disclosures deterministically."""
    with stage_run("normalize", "filing", filing_id) as (_, run):
        return {
            "run_id": str(run.id),
            "stage": run.stage_name,
            "filing_id": filing_id,
            "message": "Normalize stage scaffolded. Deterministic fact and section extraction to be added.",
        }
