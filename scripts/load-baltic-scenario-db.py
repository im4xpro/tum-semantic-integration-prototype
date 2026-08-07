#!/usr/bin/env python3
"""
Load the seeded Baltic scenario into Postgres so it can be materialised through the
normal POST /api/populate path.

The benchmark reads the sample_records embedded in data/schemas/*.json, but populate
always reads a live database — it has no sample-data option, because its job is to
materialise a whole source rather than an evaluation corpus. This script bridges the
two: it writes the same seeded rows into real tables so the editor's Populate button
produces the graph the competency-question queries in analysis/ expect.

Tables are created with the column types the schema files already declare, so running
the connector's extract_schema() against them reproduces the same ExtractedSchema.

The existing acled_data (1.6M rows) and adsb_events (2.4M rows) tables are left alone;
the scenario goes into separate baltic_* tables.

Usage:
    PYTHONPATH=src python scripts/load-baltic-scenario-db.py
    PYTHONPATH=src python scripts/load-baltic-scenario-db.py --dry-run
"""

import argparse
import json
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "src"))

from pipeline.connectors.postgres import PostgresConfig  # noqa: E402

SCHEMAS = BASE / "data" / "schemas"

# schema file -> target table. All three go to Postgres: the timeseries and stream
# sources have no dedicated store for the scenario, and populate dispatches on the
# connector name rather than on the schema's source_type.
TARGETS = [
    ("postgres_schema.json", "baltic_acled"),
    ("timescale_schema.json", "baltic_adsb"),
    ("marinetraffic_schema.json", "baltic_vessels"),
]


def coerce(value, data_type: str):
    """Empty strings become NULL. The extractor already treats '' and None identically,
    so this changes nothing downstream while keeping the table honest."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if data_type in ("bigint", "integer"):
        return int(value)
    if data_type == "double precision":
        return float(value)
    if data_type == "boolean":
        return value if isinstance(value, bool) else str(value).lower() == "true"
    return str(value)


def load(schema_file: str, table: str, dry: bool) -> None:
    schema = json.loads((SCHEMAS / schema_file).read_text())
    cols = schema["columns"]
    names = [c["name"] for c in cols]
    rows = [
        [coerce(rec.get(c["name"]), c["data_type"]) for c in cols]
        for rec in schema["sample_records"]
    ]
    print(
        f"  {table:16s} <- {schema['source_name']:24s} {len(rows)} rows x {len(names)} columns"
    )
    if dry:
        return

    cfg = PostgresConfig(table=table)  # pyright: ignore[reportCallIssue]
    ddl = ",\n    ".join(f'"{c["name"]}" {c["data_type"]}' for c in cols)
    conn = psycopg2.connect(
        host=cfg.host,
        port=cfg.port,
        dbname=cfg.database,
        user=cfg.user,
        password=cfg.password,
    )
    try:
        with conn, conn.cursor() as cur:
            cur.execute(f'DROP TABLE IF EXISTS "{table}"')
            cur.execute(f'CREATE TABLE "{table}" (\n    {ddl}\n)')
            quoted = ", ".join(f'"{n}"' for n in names)
            execute_values(cur, f'INSERT INTO "{table}" ({quoted}) VALUES %s', rows)
    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    print("Loading the seeded Baltic scenario into Postgres:")
    for schema_file, table in TARGETS:
        load(schema_file, table, args.dry_run)
    if args.dry_run:
        return
    print("\nPopulate each source from the editor with connector=postgres and:")
    for schema_file, table in TARGETS:
        src = json.loads((SCHEMAS / schema_file).read_text())["source_name"]
        print(f"    source_name={src:24s} table={table}")
    print(
        "\nThe named graph comes from source_name, not the table, so the FROM clauses"
    )
    print("in analysis/*.rq keep working unchanged.")


if __name__ == "__main__":
    main()
