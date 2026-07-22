#!/usr/bin/env python3
"""
Manual check: connect to Postgres (see .env), extract its schema, and
round-trip it through SchemaExtractor.save_schema/load_schema.
"""

from pathlib import Path

from pipeline.connectors.postgres import PostgresConfig, PostgresConnector
from pipeline.connectors.schema_extractor import SchemaExtractor

BASE_DIR = Path(__file__).parent.parent
SCHEMA_PATH = BASE_DIR / "data/schemas/postgres_schema.json"

config = PostgresConfig()

with PostgresConnector(config) as connector:
    schema = connector.extract_schema()
    print(f"Source: {schema.source_name}")
    print(f"Columns: {len(schema.columns)}")
    for col in schema.columns:
        print(f"  {col.name}: {col.data_type}")
    print("\nSample record:")
    print(schema.sample_records[0])

    schema_extractor = SchemaExtractor(connector)
    schema_extractor.save_schema(schema, SCHEMA_PATH)
    loaded_schema = schema_extractor.load_schema(SCHEMA_PATH)
    print(f"\nLoaded schema source: {loaded_schema.source_name}")
