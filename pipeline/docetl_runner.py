from __future__ import annotations

import json
import os
from pathlib import Path

import yaml

from app.docetl_runtime import (
    ensure_docetl_home,
    ensure_proxy_openai_env,
    load_repo_env,
    prefer_local_docetl_repo,
    warn_if_not_using_project_venv,
)


YAML_DIR = Path(__file__).resolve().parent / "yaml"


def _expand_env_vars(value):
    if isinstance(value, dict):
        return {key: _expand_env_vars(inner) for key, inner in value.items()}
    if isinstance(value, list):
        return [_expand_env_vars(item) for item in value]
    if isinstance(value, str):
        return os.path.expandvars(value)
    return value


def run_yaml_pipeline(
    pipeline_name: str,
    input_data: list[dict],
    input_path: Path | None = None,
    output_path: Path | None = None,
) -> list[dict]:
    """
    Run a FilingLens DocETL YAML pipeline using the standalone proxy-aware shape.
    """
    warn_if_not_using_project_venv()
    load_repo_env()
    ensure_proxy_openai_env()
    ensure_docetl_home()
    prefer_local_docetl_repo()

    from docetl.runner import DSLRunner

    yaml_path = YAML_DIR / f"{pipeline_name}.yaml"
    if not yaml_path.exists():
        raise FileNotFoundError(f"Pipeline YAML not found: {yaml_path}")

    work_dir = Path("storage/docetl_runs") / pipeline_name
    work_dir.mkdir(parents=True, exist_ok=True)

    in_path = Path(input_path) if input_path is not None else work_dir / "input.json"
    out_path = Path(output_path) if output_path is not None else work_dir / "output.json"
    intermediate_dir = work_dir / "intermediate"
    intermediate_dir.mkdir(parents=True, exist_ok=True)

    with in_path.open("w", encoding="utf-8") as handle:
        json.dump(input_data, handle, indent=2, default=str)

    config = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    config = _expand_env_vars(config)
    config["datasets"]["input"]["path"] = str(in_path.resolve())
    config["pipeline"]["output"]["path"] = str(out_path.resolve())
    config["pipeline"]["output"]["intermediate_dir"] = str(intermediate_dir.resolve())

    runner = DSLRunner(config)
    runner.load_run_save()

    if not out_path.exists():
        return []

    with out_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)
