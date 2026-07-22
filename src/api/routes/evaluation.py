from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from pipeline.evaluation.diff import diff_mappings, diff_run
from pipeline.evaluation.gold_graph import (
    build_gold_extraction_results,
    load_gold_mapping,
)
from pipeline.evaluation.models import MappingDiff, RunDiff
from pipeline.evaluation.report import evaluate_run
from pipeline.runner.experiment_manager import get_manager
from pipeline.runner.models import RunStatus

router = APIRouter()

_BASE = Path(__file__).parent.parent.parent.parent
_GOLD_STANDARD_DIR = _BASE / "data" / "gold_standard"
_SCHEMAS_DIR = _BASE / "data" / "schemas"
_ONTOLOGY_PATH = _BASE / "data" / "ontology" / "thesis_ontology.ttl"


class CompareRequest(BaseModel):
    run_ids: list[str]


def _gold_path(source_name: str) -> Path:
    p = _GOLD_STANDARD_DIR / f"{source_name}.gold.json"
    if not p.exists():
        raise HTTPException(
            404,
            f"No gold standard found for source '{source_name}' (expected {p.name})",
        )
    return p


def _load_gold(source_name: str):
    return build_gold_extraction_results(
        _gold_path(source_name), _SCHEMAS_DIR, _ONTOLOGY_PATH
    )


@router.post("/compare")
def compare_runs(req: CompareRequest) -> list[dict]:
    manager = get_manager()
    runs = [
        r
        for rid in req.run_ids
        if (r := manager.get_run(rid)) and r.status == RunStatus.completed
    ]
    if not runs:
        raise HTTPException(400, "No completed runs found for the given IDs")

    source_names = {r.config.source_name for r in runs}
    if len(source_names) > 1:
        raise HTTPException(
            400,
            f"Runs span multiple sources {source_names} — compare within one source at a time",
        )

    source_name = source_names.pop()
    gp = _gold_path(source_name)
    gold_results, gold_mapping, gold_property_ranges = build_gold_extraction_results(
        gp, _SCHEMAS_DIR, _ONTOLOGY_PATH
    )

    return [
        evaluate_run(run, gold_results, gold_mapping, gold_property_ranges).model_dump()
        for run in runs
    ]


@router.get("/diff/{run_id}")
def get_run_diff(run_id: str) -> RunDiff:
    run = get_manager().get_run(run_id)
    if not run:
        raise HTTPException(404, f"Run '{run_id}' not found")
    gold_results, gold_mapping, gold_property_ranges = _load_gold(
        run.config.source_name
    )
    return diff_run(run, gold_results, gold_mapping, gold_property_ranges)


@router.get("/mapping-diff/{run_id}")
def get_mapping_diff(run_id: str) -> MappingDiff:
    run = get_manager().get_run(run_id)
    if not run:
        raise HTTPException(404, f"Run '{run_id}' not found")
    gold_mapping = load_gold_mapping(_gold_path(run.config.source_name))
    return diff_mappings(run, gold_mapping)
