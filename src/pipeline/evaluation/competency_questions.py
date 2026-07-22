from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from pipeline.graph.graphdb_client import GraphDBClient

from .models import CQDefinition, CQResult


def load_cq_file(path: Path) -> list[CQDefinition]:
    raw = yaml.safe_load(path.read_text()) or []
    return [CQDefinition.model_validate(item) for item in raw]


def run_competency_questions(
    client: GraphDBClient,
    named_graph_uri: str,
    cqs: list[CQDefinition],
) -> list[CQResult]:
    results: list[CQResult] = []
    for cq in cqs:
        query = cq.query.replace("{{graph}}", named_graph_uri)
        try:
            if cq.query_type == "ask":
                actual = client.sparql_ask(query)
                passed = actual == cq.expected
            else:
                bindings = client.sparql_select(query)
                actual = [
                    {var: binding["value"] for var, binding in row.items()}
                    for row in bindings
                ]
                passed = _rows_equal(actual, cq.expected)
            results.append(CQResult(id=cq.id, passed=passed, actual=actual))
        except Exception as e:
            results.append(CQResult(id=cq.id, passed=False, error=str(e)))
    return results


def _rows_equal(actual: list[dict[str, Any]], expected: list[dict[str, Any]]) -> bool:
    # Order-independent: hand-authoring exact row order in YAML is error-prone.
    return _multiset(actual) == _multiset(expected)


def _multiset(rows: list[dict[str, Any]]) -> Counter:
    return Counter(frozenset(row.items()) for row in rows)
