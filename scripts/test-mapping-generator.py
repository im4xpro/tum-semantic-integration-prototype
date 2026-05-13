# scripts/test_mapping_generator.py
from pathlib import Path
from pipeline.extraction.schema_extractor import SchemaExtractor
from pipeline.ontology.manager import OntologyManager
from pipeline.mapping.mapping_generator import MappingGenerator
from pipeline.mapping.models import MappingConfig
from pipeline.mapping.llm_clients.factory import LLMProvider

BASE_DIR = Path(__file__).parent.parent

schema = SchemaExtractor(None).load_schema(BASE_DIR / "data/schemas/postgres_schema.json")
ontology_manager = OntologyManager(BASE_DIR / "data/ontology/thesis_ontology.ttl")

config = MappingConfig(
    provider=LLMProvider.FORTISS,
    llm_model="qwen3:32b",
    strategy="zero_shot",
    ontology_format="compact",
    rag_enabled=False,
    temperature=0.0,
)

generator = MappingGenerator(config)
mapping = generator.generate(schema, ontology_manager)

print(f"Source:           {mapping.source_name}")
print(f"Model:            {mapping.llm_model}")
print(f"Field mappings:   {len(mapping.field_mappings)}")
print(f"Relation mappings:{len(mapping.relation_mappings)}")
print(f"Unmapped fields:  {mapping.unmapped_fields}")
print(f"Tokens:           {mapping.prompt_tokens} prompt / {mapping.completion_tokens} completion")
print("\n--- Field Mappings ---")
for fm in mapping.field_mappings:
    status = "⚠️ " if fm.unmapped else "✅"
    print(f"{status} {fm.source_field:30s} → {fm.target_class}.{fm.target_property} [{fm.confidence:.2f}]")
print("\n--- Relation Mappings ---")
for rm in mapping.relation_mappings:
    print(f"  {rm.subject_field} --[{rm.predicate}]--> {rm.object_field}")