"""
Experiments API — trigger, monitor, and inspect pipeline runs.

Endpoints
---------
POST   /api/experiments/submit          Submit a single run config
POST   /api/experiments/preview-yaml    Parse YAML → list of run configs (dry-run)
POST   /api/experiments/submit-yaml     Parse YAML and queue all runs
GET    /api/experiments/runs            List runs (filter by experiment/status)
GET    /api/experiments/experiments     List distinct experiment names
GET    /api/experiments/runs/{id}       Get single run details
POST   /api/experiments/runs/{id}/cancel  Cancel an active run
DELETE /api/experiments/runs/{id}       Delete a finished run record
POST   /api/experiments/runs/cancel-all Cancel every active run
POST   /api/experiments/clear-all       Cancel + delete every run and wipe GraphDB
"""

from __future__ import annotations

import yaml
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from pipeline.graph.graphdb_client import GraphDBClient, GraphDBConfig, GraphDBError
from pipeline.runner.experiment_manager import get_manager
from pipeline.runner.models import (
    ExperimentConfig,
    Run,
    RunConfig,
    RunStatus,
)

router = APIRouter()


# ── Submit ────────────────────────────────────────────────────────────────────


@router.post("/submit", response_model=Run, status_code=202)
def submit_run(config: RunConfig):
    """Queue a single run immediately."""
    return get_manager().submit(config)


class YamlBody(BaseModel):
    yaml_content: str


@router.post("/preview-yaml", response_model=list[RunConfig])
def preview_yaml(body: YamlBody):
    """
    Parse an experiment YAML and return the expanded list of RunConfigs.
    Nothing is queued. Use this to verify the matrix before running.
    """
    experiment = _parse_experiment_yaml(body.yaml_content)
    return experiment.expand()


@router.post("/submit-yaml", response_model=list[Run], status_code=202)
def submit_yaml(body: YamlBody):
    """Parse an experiment YAML and queue all expanded runs."""
    experiment = _parse_experiment_yaml(body.yaml_content)
    configs = experiment.expand()
    if not configs:
        raise HTTPException(400, "YAML matrix expanded to 0 runs")
    runs = get_manager().submit_many(configs)
    return runs


# ── Query ─────────────────────────────────────────────────────────────────────


@router.get("/runs", response_model=list[Run])
def list_runs(
    experiment: str | None = Query(None, description="Filter by experiment name"),
    status: RunStatus | None = Query(None, description="Filter by status"),
    limit: int = Query(200, le=1000),
):
    return get_manager().list_runs(
        experiment_name=experiment, status=status, limit=limit
    )


@router.get("/experiments", response_model=list[str])
def list_experiments():
    """Return distinct experiment names that have runs."""
    return get_manager().list_experiments()


@router.get("/runs/{run_id}", response_model=Run)
def get_run(run_id: str):
    run = get_manager().get_run(run_id)
    if run is None:
        raise HTTPException(404, f"Run '{run_id}' not found")
    return run


# ── Control ───────────────────────────────────────────────────────────────────


@router.post("/runs/{run_id}/cancel", response_model=dict)
def cancel_run(run_id: str):
    ok = get_manager().cancel(run_id)
    if not ok:
        raise HTTPException(400, f"Run '{run_id}' is not active or does not exist")
    return {"cancelled": run_id}


@router.post("/runs/cancel-all", response_model=dict)
def cancel_all_runs():
    """Signal cancellation for every active run (best-effort — the pipeline only
    checks between phases, so an in-flight LLM call or GraphDB upload finishes first)."""
    return {"cancelled": get_manager().cancel_all()}


@router.delete("/runs/{run_id}", response_model=dict)
def delete_run(run_id: str):
    ok = get_manager().delete_run(run_id)
    if not ok:
        raise HTTPException(
            400,
            f"Run '{run_id}' not found or is still active (cancel it first)",
        )
    return {"deleted": run_id}


@router.post("/clear-all", response_model=dict)
def clear_all():
    """Cancel every active run, delete all run records, and wipe all data from GraphDB."""
    get_manager().cancel_all()
    deleted = get_manager().delete_all()
    try:
        GraphDBClient(GraphDBConfig()).clear_repository()
    except GraphDBError as e:
        raise HTTPException(
            502, f"Deleted {deleted} run(s), but clearing GraphDB failed: {e}"
        )
    return {"deleted_runs": deleted, "graphdb_cleared": True}


# ── Helpers ───────────────────────────────────────────────────────────────────


def _parse_experiment_yaml(yaml_content: str) -> ExperimentConfig:
    try:
        raw = yaml.safe_load(yaml_content)
    except yaml.YAMLError as e:
        raise HTTPException(400, f"Invalid YAML: {e}")
    try:
        return ExperimentConfig.model_validate(raw)
    except Exception as e:
        raise HTTPException(422, f"YAML structure error: {e}")
