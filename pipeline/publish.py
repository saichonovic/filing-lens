from __future__ import annotations

from pipeline.common import stage_run


def run_publish(issuer_id: str) -> dict:
    """Read from canonical and derived tables only. No new truth is created here."""
    with stage_run("publish", "issuer", issuer_id) as (_, run):
        return {
            "run_id": str(run.id),
            "stage": run.stage_name,
            "issuer_id": issuer_id,
            "message": "Publish stage scaffolded. Product surfaces should remain read-only over truth layers.",
        }
