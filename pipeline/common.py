from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy.orm import Session

from app.db import get_session
from models.base import utcnow
from models.tables import AnalysisRun


@contextmanager
def stage_run(stage_name: str, scope_type: str, scope_id: str | None, config_snapshot: dict | None = None) -> Iterator[tuple[Session, AnalysisRun]]:
    with get_session() as session:
        run = AnalysisRun(
            stage_name=stage_name,
            scope_type=scope_type,
            scope_id=scope_id,
            config_snapshot=config_snapshot,
        )
        session.add(run)
        session.flush()
        try:
            yield session, run
            run.run_status = "complete"
            run.finished_at = utcnow()
        except Exception as exc:
            run.run_status = "failed"
            run.error_summary = str(exc)
            run.finished_at = utcnow()
            raise
