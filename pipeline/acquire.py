from __future__ import annotations

from pipeline.common import stage_run


def run_acquire(issuer: str, form_type: str, limit: int = 2) -> dict:
    """Register source artifacts. Deterministic only. No interpretation."""
    with stage_run(
        stage_name="acquire",
        scope_type="issuer",
        scope_id=issuer,
        config_snapshot={"form_type": form_type, "limit": limit},
    ) as (_, run):
        return {
            "run_id": str(run.id),
            "stage": run.stage_name,
            "issuer": issuer,
            "form_type": form_type,
            "limit": limit,
            "message": "Acquire stage scaffolded. SEC fetch logic not yet implemented.",
        }
