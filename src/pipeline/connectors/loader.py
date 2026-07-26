"""Dispatch record loading across the live connectors by name.

Connection params come from .env exactly as each connector's Config already reads
them (POSTGRES_* / MONGODB_* / TIMESCALE_*); only the table/collection varies per
call. The "table" argument maps to `table` for the relational connectors and to
`collection` for MongoDB — the connectors are not identical.
"""

from __future__ import annotations

import os

from .base import BaseConnector
from .mongodb import MongoDBConfig, MongoDBConnector
from .postgres import PostgresConfig, PostgresConnector
from .timescale import TimescaleConfig, TimescaleConnector

# Optional limit for record loading, None means "load all"
_UNBOUNDED = 1_000_000


def _make_connector(connector: str, table: str) -> BaseConnector:
    if connector == "postgres":
        return PostgresConnector(
            PostgresConfig(
                host=os.getenv("POSTGRES_HOST", ""),
                database=os.getenv("POSTGRES_DATABASE", ""),
                user=os.getenv("POSTGRES_USER", ""),
                password=os.getenv("POSTGRES_PASSWORD", ""),
                table=table,
            )
        )
    if connector == "timescale":
        return TimescaleConnector(
            TimescaleConfig(
                host=os.getenv("TIMESCALE_HOST", ""),
                database=os.getenv("TIMESCALE_DATABASE", ""),
                user=os.getenv("TIMESCALE_USER", ""),
                password=os.getenv("TIMESCALE_PASSWORD", ""),
                table=table,
            )
        )
    if connector == "mongodb":
        return MongoDBConnector(
            MongoDBConfig(
                uri=os.getenv("MONGODB_URI", ""),
                database=os.getenv("MONGODB_DATABASE", ""),
                collection=table,
            )
        )
    raise ValueError(f"Unknown connector: {connector!r}")


def load_all_records(
    connector: str, table: str, limit: int | None = None
) -> list[dict]:
    """Fetch up to *limit* records (all when None) from *table* on *connector*."""
    effective_limit = limit if limit is not None else _UNBOUNDED
    with _make_connector(connector, table) as conn:
        return conn.fetch_records(effective_limit)
