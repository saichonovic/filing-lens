from __future__ import annotations

from pipeline.common import stage_run


def run_extract(filing_id: str) -> dict:
    """Convert raw artifacts to machine-readable text. Deterministic only."""
    with stage_run("extract", "filing", filing_id) as (_, run):
        return {
            "run_id": str(run.id),
            "stage": run.stage_name,
            "filing_id": filing_id,
            "message": "Extract stage scaffolded. No signal scoring or LLM work belongs here.",
        }
