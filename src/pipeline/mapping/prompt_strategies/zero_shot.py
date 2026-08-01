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
                "expression": "string: optional template that builds the subject's URI from the record, e.g. org_{actor_name}. Each {placeholder} is replaced by that column's value, so every placeholder must be an actual column name from the schema above. This is a template, not code: no f-string prefix, no quotes, no expressions inside the braces."
            },
            "type_mappings": [
                {"class_uri": "string: ontology class URI e.g. bsm:Organisation"}
            ],
            "confidence": "number 0.0-1.0: how confident you are that this is the correct entity grouping and class",
            "basis": "one of: name | description | value | structural | weak — the primary evidence for this class assignment",
            "reasoning": "string: one concrete sentence citing the specific evidence — e.g. the column/label name, the provided description, or how the grouping implies this class. No generic filler.",
            "property_mappings": [
                {
                    "property_uri": "string: ontology property URI e.g. bsm:conceptName",
                    "confidence": "number 0.0-1.0: how confident you are that this column maps to this specific property",
                    "basis": "one of: name | description | value | structural | weak — the primary evidence for this column→property choice",
                    "reasoning": "string: one concrete sentence naming the actual evidence — the column name vs property label, the column description text, or the sample values/datatype fit.",
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
- Report your confidence (0.0-1.0) that this entity grouping and class assignment are correct; tag the single best evidence category in `basis` (name, description, value, structural, or weak); and justify it in one concrete sentence citing the actual evidence — the column or label name, the provided description, or how the grouping implies the class. Do not give generic or circular justifications.
- Map each remaining field to an ontology property (property_mappings), noting whether the value is a literal or a URI.
- For each individual column-to-property mapping, report your confidence (0.0-1.0) that the column maps to that specific property; tag the single best evidence category in `basis` (name, description, value, structural, or weak); and justify it in one concrete sentence naming the actual evidence — the column name versus the property label, the column description text, or the sample values/datatype fit. Do not give generic or circular justifications.
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
