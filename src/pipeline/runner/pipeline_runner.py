"""
Execute a single pipeline run end-to-end.

Phases:
  1. Resolve mapping  → load existing OR generate via LLM
  2. Load data        → sample records from schema JSON or live DB
  3. Extract          → EntityExtractor over all records
  4. Serialize        → rdflib Graph
  5. Upload           → GraphDB named graph (replace semantics)

The cancel_event is checked between phases; if set the run is marked
cancelled and the function returns early.
"""

from __future__ import annotations

import json
import logging
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path
from typing import Literal, cast

from pipeline.connectors.postgres import PostgresConfig, PostgresConnector
from pipeline.connectors.sample_data import load_sample_records, load_schema
from pipeline.extraction.entity_extractor import EntityExtractor
from pipeline.extraction.models import ExtractionResult
from pipeline.graph.graphdb_client import GraphDBClient, GraphDBConfig
from pipeline.graph.rdf_serializer import RDFSerializer, build_property_ranges
from pipeline.mapping.descriptions import load_column_descriptions
from pipeline.mapping.mapping_generator import MappingGenerator
from pipeline.mapping.models import LLMProvider, MappingConfig, MappingDocument
from pipeline.ontology.manager import OntologyManager

from .models import Run, RunConfig, RunStatus
from .run_store import RunStore

_BASE = Path(__file__).parent.parent.parent.parent
_SCHEMAS_DIR = _BASE / "data" / "schemas"
_MAPPINGS_DIR = _BASE / "data" / "mappings"
_DESCRIPTIONS_DIR = _BASE / "data" / "descriptions"
_ONTOLOGY_PATH = _BASE / "data" / "ontology" / "thesis_ontology.ttl"

logging.getLogger("rdflib").setLevel(logging.ERROR)

sys.path.insert(0, str(_BASE / "src"))


def execute_run(run: Run, cancel: threading.Event, store: RunStore) -> Run:
    """Run the full pipeline for one RunConfig. Mutates and persists *run*."""
    run.started_at = datetime.now()
    store.save(run)

    try:
        mapping = _resolve_mapping(run, cancel, store)
        if mapping is None:
            return run

        run.mapping_id = mapping.id
        base_uri = mapping.base_uri.rstrip("/") + "/"
        run.named_graph = f"{base_uri}runs/{run.id}"
        store.save(run)

        if cancel.is_set():
            return _cancel(run, store)

        run.status = RunStatus.extracting
        store.save(run)

        records = _load_records(run)
        if run.config.data_limit:
            records = records[: run.config.data_limit]

        extractor = EntityExtractor(mapping)
        results: list[ExtractionResult] = []

        for record in records:
            if cancel.is_set():
                return _cancel(run, store)
            result = extractor.extract(record, run.config.source_name)
            results.append(result)
            run.stats.records_processed += 1
            run.stats.entities_extracted += len(result.entities)
            run.stats.relations_extracted += len(result.relations)

        ontology = OntologyManager(_ONTOLOGY_PATH).ontology
        prop_ranges = build_property_ranges(ontology)
        serializer = RDFSerializer(mapping, property_ranges=prop_ranges)
        graph = serializer.serialize_all(results)
        run.stats.triples_written = len(graph)

        if cancel.is_set():
            return _cancel(run, store)

        client = GraphDBClient(build_graphdb_config(run.config))
        client.replace_named_graph(graph, run.named_graph)
        run.stats.triples_in_db = client.count_triples(run.named_graph)

        run.status = RunStatus.completed

    except Exception:
        run.status = RunStatus.failed
        run.error = traceback.format_exc()

    finally:
        run.finished_at = datetime.now()
        run.stats.duration_seconds = (run.finished_at - run.started_at).total_seconds()
        store.save(run)

    return run


def build_graphdb_config(run_config: RunConfig) -> GraphDBConfig:
    """Build a GraphDBConfig from explicit run overrides, falling back to .env (GRAPHDB_*)."""
    overrides = run_config.graphdb.model_dump(exclude_none=True)
    return GraphDBConfig(**overrides)


def _resolve_mapping(
    run: Run, cancel: threading.Event, store: RunStore
) -> MappingDocument | None:
    """Return a MappingDocument, or None if the run was cancelled."""
    if run.config.mapping_id:
        path = _find_mapping(run.config.mapping_id)
        if path is None:
            raise FileNotFoundError(
                f"Mapping '{run.config.mapping_id}' not found in {_MAPPINGS_DIR}"
            )
        return MappingDocument.model_validate(json.loads(path.read_text()))

    run.status = RunStatus.mapping
    store.save(run)

    if cancel.is_set():
        _cancel(run, store)
        return None

    schema = load_schema(run.config.source_name, _SCHEMAS_DIR)
    descriptions = load_column_descriptions(run.config.source_name, _DESCRIPTIONS_DIR)
    generator = MappingGenerator(
        MappingConfig(
            provider=LLMProvider(run.config.provider),
            llm_model=run.config.llm_model,
            strategy=cast(
                Literal["zero_shot", "few_shot", "chain_of_thought"],
                run.config.strategy,
            ),
            ontology_format=cast(
                Literal["turtle", "compact", "class_list"],
                run.config.ontology_format,
            ),
            include_descriptions=run.config.include_descriptions,
            temperature=0.0,
        )
    )
    ontology_manager = OntologyManager(_ONTOLOGY_PATH)
    mapping = generator.generate(schema, ontology_manager, descriptions)

    fname = f"{run.config.source_name}_llm_{run.id}.json"
    (_MAPPINGS_DIR / fname).write_text(
        json.dumps(mapping.model_dump(), indent=2, default=str)
    )

    run.stats.prompt_tokens = mapping.prompt_tokens
    run.stats.completion_tokens = mapping.completion_tokens
    return mapping


def _load_records(run: Run) -> list[dict]:
    if run.config.use_sample_data:
        return load_sample_records(run.config.source_name, _SCHEMAS_DIR)

    # All connection params come from .env via PostgresConfig (POSTGRES_* env vars);
    # only the table name varies per run, so it's the only explicit kwarg here.
    config = PostgresConfig(table=run.config.source_name)
    limit = run.config.data_limit or 10_000
    with PostgresConnector(config) as conn:
        return conn.fetch_records(limit)


def _find_mapping(mapping_id: str) -> Path | None:
    for p in _MAPPINGS_DIR.glob("*.json"):
        try:
            d = json.loads(p.read_text())
            if d.get("id") == mapping_id or p.stem == mapping_id:
                return p
        except Exception:
            pass
    return None


def _cancel(run: Run, store: RunStore) -> Run:
    run.status = RunStatus.cancelled
    run.finished_at = datetime.now()
    if run.started_at:
        run.stats.duration_seconds = (run.finished_at - run.started_at).total_seconds()
    store.save(run)
    return run
