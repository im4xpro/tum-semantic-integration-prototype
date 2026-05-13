import json
from .base import BaseStrategy
from ..models import GeneratedMapping
from ...connectors.models import ExtractedSchema
from ...ontology.models import FormattedOntology


OUTPUT_SCHEMA = {
    "source_name": "string",
    "field_mappings": [
        {
            "source_field": "string — exact field name from source schema",
            "target_class": "string — ontology class URI e.g. bsm:Organisation",
            "target_property": "string — ontology property URI e.g. bsm:conceptName",
            "confidence": "float between 0.0 and 1.0",
            "reasoning": "string — one sentence explanation",
            "is_entity_creating": "bool — does this field create a new node?",
            "unmapped": "bool — true if no suitable ontology concept found"
        }
    ],
    "relation_mappings": [
        {
            "subject_field": "string — source field that is the subject",
            "predicate": "string — ontology property URI e.g. bsm:involvedActor",
            "object_field": "string — source field that is the object",
            "reasoning": "string — one sentence explanation"
        }
    ],
    "unmapped_fields": ["string — field names with no ontology match"]
}


class ZeroShotStrategy(BaseStrategy):

    def build_prompt(
        self,
        schema: ExtractedSchema,
        ontology: FormattedOntology,
    ) -> tuple[str, str]:
        system_prompt = f"""You are a semantic data integration expert. 
Your task is to map a data source schema to an OWL ontology.

For each field in the schema, determine:
- Which ontology class it helps instantiate (target_class)
- Which ontology property it maps to (target_property)
- Whether it creates a new node in the knowledge graph (is_entity_creating)
- Your confidence in the mapping (0.0 to 1.0)
- A brief reasoning for your decision

For relations, identify which fields imply a relationship between two entities.

If a field has no suitable match in the ontology, set unmapped=true and add it to unmapped_fields.

Return ONLY valid JSON matching this exact structure. No explanation, no markdown, no code blocks:
{json.dumps(OUTPUT_SCHEMA, indent=2)}"""

        schema_description = self._format_schema(schema)

        user_prompt = f"""Map the following data source schema to the ontology.

DATA SOURCE: {schema.source_name} (type: {schema.source_type})

SCHEMA:
{schema_description}

ONTOLOGY:
{ontology.content}

Return the mapping as JSON."""

        return system_prompt, user_prompt

    def _format_schema(self, schema: ExtractedSchema) -> str:
        lines = []

        if schema.columns:
            for col in schema.columns:
                lines.append(f"  {col.name}: {col.data_type}")

        if schema.inferred_fields:
            for field in schema.inferred_fields:
                lines.append(f"  {field.name}: {field.data_type}")

        if schema.sample_records:
            lines.append("\nSAMPLE RECORD:")
            sample = schema.sample_records[0]
            for k, v in list(sample.items())[:10]:
                lines.append(f"  {k}: {repr(v)[:100]}")

        return "\n".join(lines)