"""Tests for POST /api/populate and the populate runs/provenance read endpoints.

No live DB or GraphDB: the connector loader and GraphDB client are stubbed, and
the run/provenance stores are redirected to a tmp dir. Extraction + RDF
serialization run for real against the real ontology.
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from rdflib import Graph

from api.main import app
from api.routes import populate
from pipeline.connectors.base import ConnectorError
from pipeline.mapping.models import (
    MappingStatus,
    MappingDocument,
    PropertyMapping,
    PropertySource,
    SubjectMapping,
    TypeMapping,
    ValueDefinition,
)
from pipeline.runner.models import Run, RunConfig
from pipeline.runner.run_store import RunStore

client = TestClient(app)

# Deterministic target for the default base_uri + source_name "demo".
_EXPECTED_TARGET = "https://thesis.tum.de/baltic-sea-monitoring/instances/source/demo"


def _demo_mapping() -> MappingDocument:
    # Minimal but real: each row -> one bsm:Action with a conceptName literal.
    return MappingDocument(
        source_name="demo",
        status=MappingStatus.APPROVED,  # populate refuses anything else
        llm_model="manual",
        strategy="manual",
        ontology_format="manual",
        include_descriptions=False,
        subject_mappings=[
            SubjectMapping(
                subject=PropertySource(source="column", column_name="id"),
                type_mappings=[TypeMapping(class_uri="bsm:Action")],
                property_mappings=[
                    PropertyMapping(
                        property_uri="bsm:conceptName",
                        values=[
                            ValueDefinition(
                                value_source=PropertySource(
                                    source="column", column_name="name"
                                )
                            )
                        ],
                    )
                ],
            )
        ],
        generation_timestamp=datetime.now(),
        prompt_tokens=0,
        completion_tokens=0,
    )


def _body(**overrides) -> dict:
    body = {
        "mapping": _demo_mapping().model_dump(mode="json"),
        "source_name": "demo",
        "connector": "postgres",
        "table": "demo_table",
        "data_limit": None,
    }
    body.update(overrides)
    return body


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Isolate stores to tmp and stub record loading + GraphDB."""
    monkeypatch.setattr(populate, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(populate, "PROVENANCE_DIR", tmp_path / "provenance")

    records = [{"id": "r1", "name": "Alpha"}, {"id": "r2", "name": "Beta"}]
    calls = {}

    def fake_load(connector, table, limit):
        calls["load"] = {"connector": connector, "table": table, "limit": limit}
        return records

    gdb = MagicMock()
    gdb.count_triples.return_value = 4
    monkeypatch.setattr(populate, "load_all_records", fake_load)
    monkeypatch.setattr(populate, "_graphdb_client", lambda: gdb)
    return SimpleNamespace(
        runs_dir=tmp_path / "runs", records=records, calls=calls, gdb=gdb
    )


def test_populate_produces_triples_and_records_run(env):
    resp = client.post("/api/populate", json=_body())
    assert resp.status_code == 200, resp.text
    run = resp.json()["run"]

    assert run["status"] == "completed"
    assert run["config"]["origin"] == "populate"
    assert run["named_graph"] == _EXPECTED_TARGET
    assert run["stats"]["records_processed"] == 2
    assert run["stats"]["entities_extracted"] == 2
    assert run["stats"]["triples_written"] > 0
    assert run["stats"]["triples_in_db"] == 4

    # The loader was asked for the right table, and the graph was uploaded to the
    # deterministic source-keyed URI.
    assert env.calls["load"] == {
        "connector": "postgres",
        "table": "demo_table",
        "limit": None,
    }
    graph_arg, target_arg = env.gdb.replace_named_graph.call_args.args
    assert target_arg == _EXPECTED_TARGET
    assert isinstance(graph_arg, Graph) and len(graph_arg) > 0


def test_repopulate_replaces_same_source_graph(env):
    client.post("/api/populate", json=_body())
    client.post("/api/populate", json=_body())
    targets = {c.args[1] for c in env.gdb.replace_named_graph.call_args_list}
    # Both populates hit the SAME deterministic graph — replace, not accumulate.
    assert targets == {_EXPECTED_TARGET}


def test_run_listed_only_under_populate_origin(env):
    run_id = client.post("/api/populate", json=_body()).json()["run"]["id"]

    # A benchmark-origin run in the same store must not surface in the populate list.
    bench = Run(config=RunConfig(source_name="bench"))  # origin defaults to experiment
    RunStore(runs_dir=env.runs_dir).save(bench)

    listed = client.get("/api/populate/runs").json()
    ids = {r["id"] for r in listed}
    assert run_id in ids
    assert bench.id not in ids
    assert all(r["source_name"] == "demo" for r in listed)

    full = client.get(f"/api/populate/runs/{run_id}").json()
    assert full["config"]["origin"] == "populate"

    # A benchmark run id is not fetchable through the populate detail endpoint.
    assert client.get(f"/api/populate/runs/{bench.id}").status_code == 404


def test_provenance_manifest_written_and_served(env):
    run_id = client.post("/api/populate", json=_body()).json()["run"]["id"]

    manifest = client.get(f"/api/populate/runs/{run_id}/entries").json()
    assert manifest["run_id"] == run_id
    assert manifest["target_named_graph"] == _EXPECTED_TARGET
    assert manifest["entry_count"] == 2

    entries = manifest["entries"]
    assert len(entries) == 2
    by_record = {e["source_record_id"]: e for e in entries}
    assert set(by_record) == {"r1", "r2"}
    for e in entries:
        assert e["class_uri"] == "bsm:Action"
        assert e["subject_uri"].startswith(
            "https://thesis.tum.de/baltic-sea-monitoring/instances/"
        )


def test_missing_provenance_and_run_return_404(env):
    assert client.get("/api/populate/runs/nope/entries").status_code == 404
    assert client.get("/api/populate/runs/nope").status_code == 404


def test_connector_error_returns_502_and_records_failed_run(env, monkeypatch):
    def boom(connector, table, limit):
        raise ConnectorError("cannot reach db")

    monkeypatch.setattr(populate, "load_all_records", boom)

    resp = client.post("/api/populate", json=_body())
    assert resp.status_code == 502
    assert "cannot reach db" in resp.json()["detail"]

    # The failed run is still recorded for the operator to see.
    failed = [
        r for r in client.get("/api/populate/runs").json() if r["status"] == "failed"
    ]
    assert len(failed) == 1
    env.gdb.replace_named_graph.assert_not_called()


def test_table_defaults_to_source_name(env):
    client.post("/api/populate", json=_body(table=None))
    assert env.calls["load"]["table"] == "demo"


@pytest.mark.parametrize("status", ["draft", "rejected", "superseded"])
def test_populate_refuses_unapproved_mapping(env, status):
    """Only an approved mapping may be materialised (REQ-HITL-FR-02).

    The refusal happens before any work: no connector call, no graph write, and — since
    a rejected request is not a failed run — no run record either.
    """
    body = _body()
    body["mapping"]["status"] = status

    resp = client.post("/api/populate", json=body)

    assert resp.status_code == 409, resp.text
    assert status in resp.json()["detail"]
    env.gdb.replace_named_graph.assert_not_called()
    assert "load" not in env.calls
    assert client.get("/api/populate/runs").json() == []


def test_status_survives_the_request_boundary(env):
    """The gate is only meaningful if the field is not silently dropped on the way in."""
    body = _body()
    body["mapping"]["status"] = "approved"
    assert client.post("/api/populate", json=body).status_code == 200

    # A mapping that omits status entirely defaults to draft, i.e. fails closed.
    body = _body()
    del body["mapping"]["status"]
    assert client.post("/api/populate", json=body).status_code == 409
