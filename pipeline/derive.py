from __future__ import annotations

from pipeline.common import stage_run


def run_derive(issuer_id: str, signals: str = "all") -> dict:
    """Run signal engines. Deterministic gating precedes any LLM support."""
    with stage_run(
        "derive",
        "issuer",
        issuer_id,
        config_snapshot={"signals": signals},
    ) as (_, run):
        return {
            "run_id": str(run.id),
            "stage": run.stage_name,
            "issuer_id": issuer_id,
            "signals": signals,
            "message": "Derive stage scaffolded. Signal engines will attach evidence before verdicts.",
        }
