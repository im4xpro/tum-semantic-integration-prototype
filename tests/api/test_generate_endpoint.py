"""Tests for POST /api/mappings/generate.

The LLM client is always stubbed — these tests never make a real provider call.
They assert the endpoint's two contractual guarantees: it returns a mapping with
confidence/reasoning at both levels, and it has no side effects (nothing is written
to the data/mappings/ benchmark corpus), plus that an unparseable LLM response
surfaces as 502 rather than a 500/stack trace.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.deps import MAPPINGS_DIR
from api.main import app

# A well-formed LLM response carrying confidence/reasoning at subject and property level.
_LLM_JSON = json.dumps(
    {
        "subject_mappings": [
            {
                "subject": {"source": "column", "column_name": "order_id"},
                "type_mappings": [{"class_uri": "bsm:Action"}],
                "confidence": 0.82,
                "reasoning": "order_id identifies one action per row.",
                "property_mappings": [
                    {
                        "property_uri": "bsm:conceptName",
                        "confidence": 0.9,
                        "reasoning": "notes column is the human-readable name.",
                        "values": [
                            {
                                "value_source": {
                                    "source": "column",
                                    "column_name": "notes",
                                }
                            }
                        ],
                    }
                ],
            }
        ],
        "unmapped_fields": [],
    }
)

_REQUEST_BODY = {
    "source_schema": {
        "source_name": "demo_source",
        "source_type": "csv",  # deliberately outside the connector Literal
        "columns": [
            {"name": "order_id", "data_type": "text"},
            {"name": "notes", "data_type": "text"},
        ],
        "inferred_fields": [],
        "sample_records": [{"order_id": "A1", "notes": "hello"}],
    },
    "strategy": "zero_shot",
    "provider": "openrouter",
    "llm_model": "test-model",
    "ontology_format": "compact",
    "include_descriptions": False,
}

client = TestClient(app)


@pytest.fixture
def stub_llm():
    """Patch the LLM factory so generation never hits a real provider.

    Yields the mock client whose .complete(...) return value the test sets."""
    with patch("pipeline.mapping.mapping_generator.LLMClientFactory.create") as create:
        mock_client = MagicMock()
        create.return_value = mock_client
        yield mock_client


def test_generate_returns_confidence_and_does_not_persist(stub_llm):
    stub_llm.complete.return_value = (_LLM_JSON, 100, 40)
    before = set(MAPPINGS_DIR.glob("*.json"))

    resp = client.post("/api/mappings/generate", json=_REQUEST_BODY)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    subject = body["subject_mappings"][0]
    assert subject["confidence"] == 0.82
    assert subject["reasoning"]
    prop = subject["property_mappings"][0]
    assert prop["confidence"] == 0.9
    assert prop["reasoning"]

    # No side effect: the benchmark corpus is untouched.
    assert set(MAPPINGS_DIR.glob("*.json")) == before


def test_unparseable_response_maps_to_502(stub_llm):
    stub_llm.complete.return_value = ("this is not JSON at all", 10, 2)

    resp = client.post("/api/mappings/generate", json=_REQUEST_BODY)

    assert resp.status_code == 502, resp.text
