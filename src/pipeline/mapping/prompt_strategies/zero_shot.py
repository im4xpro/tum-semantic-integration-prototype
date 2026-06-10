import json
from .base import BaseStrategy
from ...connectors.models import ExtractedSchema
from ...ontology.models import FormattedOntology


OUTPUT_SCHEMA = {
    "subject_mappings": [
        {
            "subject": {
                "source": "column | constant",
                "column_name": "string: column that provides the subject URI (omit if source=constant)",
                "constant_value": "string: fixed URI for the subject (omit if source=column)"
            },
            "subject_transformation": {
                "expression": "string: optional Python expression to build the URI, e.g. f'bsm:org/{value}'"
            },
            "type_mappings": [
                {"class_uri": "string: ontology class URI e.g. bsm:Organisation"}
            ],
            "property_mappings": [
                {
                    "property_uri": "string: ontology property URI e.g. bsm:conceptName",
                    "values": [
                        {
                            "value_source": {
                                "source": "column | constant",
                                "column_name": "string: source column name",
                                "constant_value": "string: fixed value"
                            },
                            "transformation": None,
                            "value_type": {
                                "type": "literal | iri",
                                "type_mappings": [],
                                "property_mappings": []
                            }
                        }
                    ]
                }
            ]
        }
    ],
    "unmapped_fields": ["string: field names with no suitable ontology match"]
}


class ZeroShotStrategy(BaseStrategy):

    def build_prompt(
        self,
        schema: ExtractedSchema,
        ontology: FormattedOntology,
    ) -> tuple[str, str]:
        system_prompt = f"""You are a semantic data integration expert.
Your task is to map a data source schema to an OWL ontology using an RML-style subject-centric structure.

Group fields by the entity they describe. For each entity type:
- Identify which column or constant value serves as the subject (entity identifier).
- Specify the ontology class (type_mappings).
- Map each remaining field to an ontology property (property_mappings), noting whether the value is a literal or a URI.
- If a value points to another entity, set value_type to "iri" and include nested type_mappings/property_mappings if applicable.
- If a field cannot be mapped to any ontology concept, add it to unmapped_fields.

Omit subject_transformation and transformation when no expression is needed.

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