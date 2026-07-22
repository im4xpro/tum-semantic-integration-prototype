import json

from ...connectors.models import ExtractedSchema
from ...ontology.manager import OntologyManager
from ...ontology.models import FormattedOntology
from .base import BasePromptStrategy

OUTPUT_SCHEMA = {
    "subject_mappings": [
        {
            "subject": {
                "source": "column | constant",
                "column_name": "string: column that provides the subject URI (omit if source=constant)",
                "constant_value": "string: fixed URI for the subject (omit if source=column)",
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
                                "constant_value": "string: fixed value",
                            },
                            "transformation": None,
                            "value_type": {
                                "type": "literal | iri",
                                "type_mappings": [],
                                "property_mappings": [],
                            },
                        }
                    ],
                }
            ],
        }
    ],
    "unmapped_fields": ["string: field names with no suitable ontology match"],
}


class ZeroShotPromptStrategy(BasePromptStrategy):
    def build_prompt(
        self,
        schema: ExtractedSchema,
        ontology: FormattedOntology,
        column_descriptions: dict[str, str] | None = None,
        ontology_manager: OntologyManager | None = None,
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

        schema_description = self._format_schema(schema, column_descriptions)

        user_prompt = f"""Map the following data source schema to the ontology.

DATA SOURCE: {schema.source_name} (type: {schema.source_type})

SCHEMA:
{schema_description}

ONTOLOGY:
{ontology.content}

{self._closing_instruction()}"""

        return system_prompt, user_prompt

    def _closing_instruction(self) -> str:
        return "Return the mapping as JSON."

    def _format_schema(
        self,
        schema: ExtractedSchema,
        column_descriptions: dict[str, str] | None = None,
    ) -> str:
        lines = []
        descriptions = column_descriptions or {}

        for field in [*schema.columns, *schema.inferred_fields]:
            desc = descriptions.get(field.name)
            suffix = f" — {desc}" if desc else ""
            lines.append(f"  {field.name}: {field.data_type}{suffix}")

        if schema.sample_records:
            lines.append("\nSAMPLE RECORD:")
            sample = schema.sample_records[0]
            for k, v in sample.items():
                lines.append(f"  {k}: {repr(v)[:100]}")

        return "\n".join(lines)
