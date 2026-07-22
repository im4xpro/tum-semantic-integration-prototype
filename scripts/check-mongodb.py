#!/usr/bin/env python3
"""
Manual check: connect to MongoDB (see .env), extract its schema, and
round-trip it through SchemaExtractor.save_schema/load_schema.
"""

from pathlib import Path

from pipeline.connectors.mongodb import MongoDBConfig, MongoDBConnector
from pipeline.connectors.schema_extractor import SchemaExtractor

BASE_DIR = Path(__file__).parent.parent
SCHEMA_PATH = BASE_DIR / "data/schemas/mongodb_schema.json"

config = MongoDBConfig()

with MongoDBConnector(config) as connector:
    schema = connector.extract_schema()
    print(f"Source: {schema.source_name}")
    print(f"Inferred fields: {len(schema.inferred_fields)}")
    for field in schema.inferred_fields:
        print(f"  {field.name}: {field.data_type}")
    print("\nSample record:")
    print(schema.sample_records[0])

    schema_extractor = SchemaExtractor(connector)
    schema_extractor.save_schema(schema, SCHEMA_PATH)
    loaded_schema = schema_extractor.load_schema(SCHEMA_PATH)
    print(f"\nLoaded schema source: {loaded_schema.source_name}")
