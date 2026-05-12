from pipeline.connectors.postgres import PostgresConnector, PostgresConfig
from pipeline.extraction.schema_extractor import SchemaExtractor

config = PostgresConfig()

# Test connector
with PostgresConnector(config) as connector:
    schema = connector.extract_schema()
    print(f"Source: {schema.source_name}")
    print(f"Columns: {len(schema.columns)}")
    for col in schema.columns:
        print(f"  {col.name}: {col.data_type}")
    print(f"\nSample record:")
    print(schema.sample_records[0])

# Test schema extractor
schema_extractor = SchemaExtractor(connector)
schema_extractor.save_schema(schema, "data/schemas/postgres_schema.json")
loaded_schema = schema_extractor.load_schema("data/schemas/postgres_schema.json")
print(f"\nLoaded schema source: {loaded_schema.source_name}")