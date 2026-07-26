"""
Populate API — operator-triggered materialization of one mapping into GraphDB.

Synchronous and separate from the async experiment/benchmark path: each call
applies exactly ONE mapping to exactly ONE source and replaces that source's
named graph. Nothing ingests automatically (REQ-HITL-FR-02) and every created
subject is recorded against its source record (REQ-PROV-FR-02).

Endpoints
---------
POST   /api/populate                     Materialize a mapping into a source graph
GET    /api/populate/runs                Populate runs, newest first (summaries)
GET    /api/populate/runs/{id}           Full populate run
GET    /api/populate/runs/{id}/entries   Subject→record provenance manifest
"""

from __future__ import annotations

import re
import traceback
import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from pipeline.connectors.base import ConnectorError
from pipeline.connectors.loader import load_all_records
from pipeline.extraction.entity_extractor import EntityExtractor
from pipeline.graph.graphdb_client import GraphDBClient, GraphDBConfig, GraphDBError
from pipeline.graph.rdf_serializer import RDFSerializer, build_property_ranges
from pipeline.mapping.models import MappingDocument
from pipeline.runner.models import Run, RunConfig, RunStatus
from pipeline.runner.provenance import (
    ProvenanceEntry,
    ProvenanceManifest,
    ProvenanceStore,
)
from pipeline.runner.run_store import RunStore

from ..deps import DATA_DIR, get_ontology_manager

router = APIRouter()

# Module-level so tests can redirect persistence to a tmp dir. In production these
# match the runner defaults: populate runs share data/runs with benchmark runs and
# are distinguished by RunConfig.origin.
RUNS_DIR = DATA_DIR / "runs"
PROVENANCE_DIR = DATA_DIR / "provenance"


class PopulateRequest(BaseModel):
    # The mapping is sent inline (full document), never read from data/mappings/ —
    # editor mappings must not land in the benchmark corpus.
    mapping: MappingDocument
    source_name: str  # logical source; used for the named graph + record loading
    connector: Literal["postgres", "mongodb", "timescale"]
    table: str | None = None  # table/collection name; defaults to source_name
    data_limit: int | None = None  # operator caps rows manually


class PopulateResponse(BaseModel):
    run: Run
    provenance_path: str


class PopulateRunSummary(BaseModel):
    id: str
    source_name: str
    mapping_id: str | None
    status: RunStatus
    records_processed: int
    entities_extracted: int
    relations_extracted: int
    triples_in_db: int
    created_at: datetime
    target_named_graph: str | None


def _run_store() -> RunStore:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    return RunStore(runs_dir=RUNS_DIR)


def _provenance_store() -> ProvenanceStore:
    return ProvenanceStore(PROVENANCE_DIR)


def _graphdb_client() -> GraphDBClient:
    return GraphDBClient(GraphDBConfig())


def _slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9_-]+", "-", name.strip().lower()).strip("-")
    return slug or "source"


def _target_graph(base_uri: str, source_name: str) -> str:
    # Deterministic per-source URI: re-populating the same source hits the same
    # graph, so replace_named_graph makes repeat populates idempotent.
    return f"{base_uri.rstrip('/')}/source/{_slug(source_name)}"


def _finalize(run: Run) -> None:
    run.finished_at = datetime.now()
    if run.started_at:
        run.stats.duration_seconds = (run.finished_at - run.started_at).total_seconds()


def _summary(run: Run) -> PopulateRunSummary:
    return PopulateRunSummary(
        id=run.id,
        source_name=run.config.source_name,
        mapping_id=run.mapping_id,
        status=run.status,
        records_processed=run.stats.records_processed,
        entities_extracted=run.stats.entities_extracted,
        relations_extracted=run.stats.relations_extracted,
        triples_in_db=run.stats.triples_in_db,
        created_at=run.created_at,
        target_named_graph=run.named_graph,
    )


@router.post("", response_model=PopulateResponse)
def populate(req: PopulateRequest) -> PopulateResponse:
    mapping = req.mapping
    if not mapping.id:
        mapping.id = str(uuid.uuid4())
    table = req.table or req.source_name
    target = _target_graph(mapping.base_uri, req.source_name)

    run = Run(
        config=RunConfig(
            origin="populate",
            source_name=req.source_name,
            use_sample_data=False,
            data_limit=req.data_limit,
            mapping_id=mapping.id,
        ),
        mapping_id=mapping.id,
        named_graph=target,
        status=RunStatus.extracting,
        started_at=datetime.now(),
    )
    store = _run_store()

    try:
        records = load_all_records(req.connector, table, req.data_limit)

        extractor = EntityExtractor(mapping)
        results = [extractor.extract(record, req.source_name) for record in records]
        run.stats.records_processed = len(results)
        run.stats.entities_extracted = sum(len(r.entities) for r in results)
        run.stats.relations_extracted = sum(len(r.relations) for r in results)

        ontology = get_ontology_manager().ontology
        prop_ranges = build_property_ranges(ontology)
        graph = RDFSerializer(mapping, property_ranges=prop_ranges).serialize_all(
            results
        )
        run.stats.triples_written = len(graph)

        client = _graphdb_client()
        client.replace_named_graph(graph, target)  # clear + upload → idempotent
        run.stats.triples_in_db = client.count_triples(target)

        run.status = RunStatus.completed
        _finalize(run)
        store.save(run)

        manifest = ProvenanceManifest(
            run_id=run.id,
            source_name=req.source_name,
            connector=req.connector,
            mapping_id=mapping.id,
            mapping_name=mapping.source_name,
            target_named_graph=target,
            created_at=run.created_at,
            entry_count=run.stats.entities_extracted,
            entries=[
                ProvenanceEntry(
                    subject_uri=entity.subject_uri,
                    source_record_id=entity.source_record_id,
                    class_uri=entity.class_uri,
                )
                for result in results
                for entity in result.entities
            ],
        )
        path = _provenance_store().save(manifest)
        return PopulateResponse(run=run, provenance_path=str(path))

    except Exception as e:
        # Persist the failed run either way so the operator sees it in the list,
        # then surface expected connector/GraphDB failures as 502. Unexpected
        # errors propagate (500 + real traceback) rather than being masked.
        run.status = RunStatus.failed
        run.error = traceback.format_exc()
        _finalize(run)
        store.save(run)
        if isinstance(e, (ConnectorError, GraphDBError)):
            raise HTTPException(status_code=502, detail=str(e)) from e
        raise


@router.get("/runs", response_model=list[PopulateRunSummary])
def list_populate_runs() -> list[PopulateRunSummary]:
    # list_all() is newest-first; keep only populate-origin runs so benchmark
    # runs never bleed into what the editor consumes.
    return [
        _summary(run)
        for run in _run_store().list_all()
        if run.config.origin == "populate"
    ]


@router.get("/runs/{run_id}", response_model=Run)
def get_populate_run(run_id: str) -> Run:
    run = _run_store().load(run_id)
    if run is None or run.config.origin != "populate":
        raise HTTPException(404, f"Populate run '{run_id}' not found")
    return run


@router.get("/runs/{run_id}/entries", response_model=ProvenanceManifest)
def get_populate_run_entries(run_id: str) -> ProvenanceManifest:
    manifest = _provenance_store().load(run_id)
    if manifest is None:
        raise HTTPException(404, f"No provenance manifest for run '{run_id}'")
    return manifest
