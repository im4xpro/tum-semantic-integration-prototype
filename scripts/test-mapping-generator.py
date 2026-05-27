# scripts/test_mapping_generator.py
from pathlib import Path
from pipeline.connectors.schema_extractor import SchemaExtractor
from pipeline.ontology.manager import OntologyManager
from pipeline.mapping.mapping_generator import MappingGenerator
from pipeline.mapping.models import MappingConfig
from pipeline.mapping.llm_clients.factory import LLMProvider

BASE_DIR = Path(__file__).parent.parent

schema = SchemaExtractor(None).load_schema(BASE_DIR / "data/schemas/postgres_schema.json")
ontology_manager = OntologyManager(BASE_DIR / "data/ontology/thesis_ontology.ttl")

config = MappingConfig(
    provider=LLMProvider.FORTISS,
    llm_model="llama3.2:latest",
    strategy="zero_shot",
    ontology_format="compact",
    rag_enabled=False,
    temperature=0.0,
)
# config = MappingConfig(
#     provider=LLMProvider.OLLAMA,
#     llm_model="llama3.2:latest ",
#     strategy="zero_shot",
#     ontology_format="compact",
#     rag_enabled=False,
#     temperature=0.0,
# )

generator = MappingGenerator(config)
mapping = generator.generate(schema, ontology_manager)

print(f"Source:           {mapping.source_name}")
print(f"Model:            {mapping.llm_model}")
print(f"Subject mappings: {len(mapping.subject_mappings)}")
print(f"Unmapped fields:  {mapping.unmapped_fields}")
print(f"Tokens:           {mapping.prompt_tokens} prompt / {mapping.completion_tokens} completion")
print("\n--- Subject Mappings ---")
for sm in mapping.subject_mappings:
    subject = sm.subject.column_name or sm.subject.constant_value
    classes = ", ".join(t.class_uri for t in sm.type_mappings)
    print(f"  [{classes}] subject={subject}")
    for pm in sm.property_mappings:
        for v in pm.values:
            col = v.value_source.column_name or v.value_source.constant_value
            print(f"    {pm.property_uri:50s} <- {col} ({v.value_type.value_type})")