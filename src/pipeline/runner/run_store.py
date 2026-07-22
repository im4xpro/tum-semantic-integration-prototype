"""Persistent run store backed by one JSON file per run in data/runs/."""

from __future__ import annotations

import json
import threading
from pathlib import Path

from .models import Run, RunStatus

_RUNS_DIR = Path(__file__).parent.parent.parent.parent / "data" / "runs"
_RUNS_DIR.mkdir(parents=True, exist_ok=True)


class RunStore:
    """Thread-safe store for Run objects persisted to disk."""

    def __init__(self, runs_dir: Path = _RUNS_DIR):
        self._dir = runs_dir
        self._lock = threading.Lock()

    # ── Write ─────────────────────────────────────────────────────────────────

    def save(self, run: Run) -> None:
        path = self._dir / f"{run.id}.json"
        data = run.model_dump(mode="json")
        with self._lock:
            path.write_text(json.dumps(data, indent=2, default=str))

    def delete(self, run_id: str) -> bool:
        path = self._dir / f"{run_id}.json"
        with self._lock:
            if path.exists():
                path.unlink()
                return True
        return False

    # ── Read ──────────────────────────────────────────────────────────────────

    def load(self, run_id: str) -> Run | None:
        path = self._dir / f"{run_id}.json"
        if not path.exists():
            return None
        with self._lock:
            data = json.loads(path.read_text())
        return Run.model_validate(data)

    def list_all(self) -> list[Run]:
        """Return all runs sorted newest-first."""
        runs = []
        with self._lock:
            paths = sorted(self._dir.glob("*.json"), reverse=True)
        for p in paths:
            try:
                runs.append(Run.model_validate(json.loads(p.read_text())))
            except Exception:
                pass
        return runs

    def list_by_experiment(self, experiment_name: str) -> list[Run]:
        return [
            r for r in self.list_all() if r.config.experiment_name == experiment_name
        ]

    # ── Startup recovery ──────────────────────────────────────────────────────

    def mark_interrupted_as_failed(self) -> list[str]:
        """
        Any run left in queued/mapping/extracting state means the server was
        restarted mid-run. Mark them failed so they don't appear stuck.
        """
        in_progress = {RunStatus.queued, RunStatus.mapping, RunStatus.extracting}
        marked = []
        for run in self.list_all():
            if run.status in in_progress:
                run.status = RunStatus.failed
                run.error = "Server restarted while run was in progress"
                self.save(run)
                marked.append(run.id)
        return marked
