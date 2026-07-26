"""Tests for the connector dispatch used by populate — no live DB is touched.

Verifies each connector name maps to the right config field (table vs collection)
and that None limit becomes the high 'all' cap.
"""

from unittest.mock import MagicMock

import pytest

from pipeline.connectors import loader


@pytest.fixture
def capture(monkeypatch):
    """Patch every connector+config so dispatch is observable without a DB."""
    made = {}
    conn = MagicMock()
    conn.__enter__.return_value = conn
    conn.__exit__.return_value = False
    conn.fetch_records.return_value = [{"row": 1}]

    def connector_factory(kind):
        def make(config):
            made["kind"] = kind
            made["config"] = config
            return conn

        return make

    monkeypatch.setattr(
        loader, "PostgresConfig", lambda **kw: {"cfg": "postgres", **kw}
    )
    monkeypatch.setattr(
        loader, "TimescaleConfig", lambda **kw: {"cfg": "timescale", **kw}
    )
    monkeypatch.setattr(loader, "MongoDBConfig", lambda **kw: {"cfg": "mongodb", **kw})
    monkeypatch.setattr(loader, "PostgresConnector", connector_factory("postgres"))
    monkeypatch.setattr(loader, "TimescaleConnector", connector_factory("timescale"))
    monkeypatch.setattr(loader, "MongoDBConnector", connector_factory("mongodb"))
    return made, conn


def test_postgres_uses_table(capture):
    made, conn = capture
    out = loader.load_all_records("postgres", "events", limit=5)
    assert out == [{"row": 1}]
    assert made["config"]["cfg"] == "postgres"
    assert made["config"]["table"] == "events"  # relational -> table
    assert "collection" not in made["config"]
    conn.fetch_records.assert_called_once_with(5)


def test_timescale_uses_table(capture):
    made, conn = capture
    loader.load_all_records("timescale", "ticks", limit=10)
    assert made["config"]["cfg"] == "timescale"
    assert made["config"]["table"] == "ticks"
    conn.fetch_records.assert_called_once_with(10)


def test_mongodb_uses_collection(capture):
    made, conn = capture
    loader.load_all_records("mongodb", "entities", limit=3)
    assert made["config"]["cfg"] == "mongodb"
    assert made["config"]["collection"] == "entities"  # document -> collection
    assert "table" not in made["config"]
    conn.fetch_records.assert_called_once_with(3)


def test_none_limit_becomes_high_cap(capture):
    _, conn = capture
    loader.load_all_records("postgres", "events", limit=None)
    conn.fetch_records.assert_called_once_with(loader._UNBOUNDED)


def test_unknown_connector_raises():
    with pytest.raises(ValueError):
        loader.load_all_records("cassandra", "t", limit=1)
