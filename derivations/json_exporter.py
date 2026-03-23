from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def export_issuer_json(report: dict, output_dir: str = "storage/exports") -> Path:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    ticker = report["issuer"]["ticker"]
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = Path(output_dir) / f"{ticker}_{timestamp}.json"
    with path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, default=str)
    return path
