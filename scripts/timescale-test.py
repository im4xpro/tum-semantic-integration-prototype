from pipeline.connectors.timescale import TimescaleConnector, TimescaleConfig

config = TimescaleConfig()

with TimescaleConnector(config) as connector:
    schema = connector.extract_schema()
    print(f"Source: {schema.source_name}")
    print(f"Type: {schema.source_type}")
    print(f"Columns: {len(schema.columns)}")
    for col in schema.columns:
        print(f"  {col.name}: {col.data_type}")
    print(f"\nSample record:")
    print(schema.sample_records[0])