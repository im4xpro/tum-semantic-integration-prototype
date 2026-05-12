from pipeline.connectors.timescale import TimescaleConnector, TimescaleConfig
from pipeline.extraction.schema_extractor import SchemaExtractor

config = TimescaleConfig()

# Test connector
with TimescaleConnector(config) as connector:
    schema = connector.extract_schema()
    print(f"Source: {schema.source_name}")
    print(f"Type: {schema.source_type}")
    print(f"Columns: {len(schema.columns)}")
    for col in schema.columns:
        print(f"  {col.name}: {col.data_type}")
    print(f"\nSample record:")
    print(schema.sample_records[0])
    
# Test schema extractor

schema_extractor = SchemaExtractor(connector)
schema_extractor.save_schema(schema, "data/schemas/timescale_schema.json")
loaded_schema = schema_extractor.load_schema("data/schemas/timescale_schema.json")
print(f"\nLoaded schema source: {loaded_schema.source_name}")