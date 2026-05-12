from pipeline.connectors.mongodb import MongoDBConnector, MongoDBConfig
import ast

config = MongoDBConfig()

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