from pipeline.connectors.mongodb import MongoDBConnector, MongoDBConfig
import ast

from pipeline.extraction.schema_extractor import SchemaExtractor

config = MongoDBConfig()

# Test connector
with MongoDBConnector(config) as connector:
    schema = connector.extract_schema()
    
    # Debug — Schema-Properties gruppiert ausgeben
    samples = list(connector._collection.aggregate([{"$sample": {"size": 50}}]))
    
    schema_properties: dict[str, set] = {}
    for doc in samples:
        schema_type = doc.get("schema", "Unknown")
        props = doc.get("properties", {})
        
        if schema_type not in schema_properties:
            schema_properties[schema_type] = set()
        
        for key in props.keys():
            schema_properties[schema_type].add(key)
    
    for schema_type, fields in schema_properties.items():
        print(f"\n{schema_type}:")
        for field in sorted(fields):
            print(f"  properties.{field}")

# Test schema extractor
schema_extractor = SchemaExtractor(connector)
schema_extractor.save_schema(schema, "data/schemas/mongodb_schema.json")
loaded_schema = schema_extractor.load_schema("data/schemas/mongodb_schema.json")
print(f"\nLoaded schema source: {loaded_schema.source_name}")