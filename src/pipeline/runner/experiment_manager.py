"""
ExperimentManager: singleton that owns the thread pool and run lifecycle.

- Accepts RunConfig → creates Run → dispatches to ThreadPoolExecutor
- Supports cancellation via per-run threading.Event
- Persists all state through RunStore (survives API restarts)
"""
from __future__ import annotations

import logging
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Optional

from .models import Run, RunConfig, RunStatus
from .pipeline_runner import execute_run
from .run_store import RunStore


class ExperimentManager:

    def __init__(self, max_concurrent: int = 2):
        self._store = RunStore()
        self._pool = ThreadPoolExecutor(max_workers=max_concurrent, thread_name_prefix="pipeline")
        self._cancel_events: dict[str, threading.Event] = {}
        self._futures: dict[str, Future] = {}
        self._lock = threading.Lock()

        # Recover: any run stuck in-progress from a previous process lifetime
        interrupted = self._store.mark_interrupted_as_failed()
        if interrupted:
            logging.getLogger(__name__).warning(
                "Marked %d interrupted runs as failed: %s", len(interrupted), interrupted
            )

    # ── Submit ────────────────────────────────────────────────────────────────

    def submit(self, config: RunConfig) -> Run:
        """Queue one run and return the Run object immediately."""
        run = Run(config=config)
        self._store.save(run)

        cancel = threading.Event()
        with self._lock:
            self._cancel_events[run.id] = cancel

        future = self._pool.submit(self._execute, run, cancel)
        with self._lock:
            self._futures[run.id] = future

        return run

    def submit_many(self, configs: list[RunConfig]) -> list[Run]:
        """Queue multiple runs. Returns list of Run objects."""
        return [self.submit(c) for c in configs]

    # ── Cancel ────────────────────────────────────────────────────────────────

    def cancel(self, run_id: str) -> bool:
        """Signal cancellation. Returns False if run is not active."""
        with self._lock:
            event = self._cancel_events.get(run_id)
            future = self._futures.get(run_id)

        if event is None:
            # Run might be queued but not yet started; mark directly
            run = self._store.load(run_id)
            if run and run.status == RunStatus.queued:
                run.status = RunStatus.cancelled
                self._store.save(run)
                return True
            return False

        event.set()

        # If the future hasn't started yet, cancel it
        if future:
            future.cancel()

        return True

    # ── Query ─────────────────────────────────────────────────────────────────

    def get_run(self, run_id: str) -> Run | None:
        return self._store.load(run_id)

    def list_runs(
        self,
        experiment_name: str | None = None,
        status: RunStatus | None = None,
        limit: int = 200,
    ) -> list[Run]:
        runs = self._store.list_all()
        if experiment_name:
            runs = [r for r in runs if r.config.experiment_name == experiment_name]
        if status:
            runs = [r for r in runs if r.status == status]
        return runs[:limit]

    def list_experiments(self) -> list[str]:
        """Return distinct experiment names, sorted."""
        names = {r.config.experiment_name for r in self._store.list_all()}
        return sorted(names)

    def delete_run(self, run_id: str) -> bool:
        """Delete a completed/failed/cancelled run record."""
        run = self._store.load(run_id)
        if run is None:
            return False
        if run.status in {RunStatus.queued, RunStatus.mapping, RunStatus.extracting}:
            return False  # refuse to delete active runs
        self._store.delete(run_id)
        return True

    # ── Internals ─────────────────────────────────────────────────────────────

    def _execute(self, run: Run, cancel: threading.Event) -> None:
        try:
            execute_run(run, cancel, self._store)
        finally:
            with self._lock:
                self._cancel_events.pop(run.id, None)
                self._futures.pop(run.id, None)

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)


# ── Module-level singleton ────────────────────────────────────────────────────

_manager: Optional[ExperimentManager] = None


def get_manager() -> ExperimentManager:
    global _manager
    if _manager is None:
        _manager = ExperimentManager(max_concurrent=2)
    return _manager
