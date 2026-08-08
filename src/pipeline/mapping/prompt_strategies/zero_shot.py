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
                            "transformation": {
                                "expression": "string: optional template that builds this value from the record, same rules as subject_transformation. When value_type is 'iri' this MUST be byte-for-byte identical to the subject_transformation of the entity being referenced, otherwise the relation does not resolve. Omit when the raw column value is used as-is."
                            },
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

# Mechanical constraints of the target format. Shared verbatim by every strategy so
# that the strategy comparison varies only in how the task is framed (plain, worked
# example, step-by-step) and never in what the model is told about the format itself.
SHARED_RULES = """
Rules of the target format:
- Use only classes and properties that appear in the ontology below, written exactly as
  the ontology writes them. Do not invent, rename, or guess terms; if nothing fits, leave
  the field unmapped rather than inventing a term.
- A subject's expression must yield a distinct value for every distinct real-world entity.
  Two records that produce the same expression are treated as the same entity and merged.
- An expression is a plain {column} template, nothing more: no arithmetic, no function
  calls, no format specifiers such as {value:.2f}. Literal text around the placeholders
  is kept as-is. Anything else evaluates to nothing and the entity or value is dropped.
- If any column referenced by an expression is empty for a record, the whole entity or
  value is silently skipped for that record. Prefer columns that are populated in every
  record for subjects; a sparsely filled column will discard most of the data.
- When value_type is "iri", the value's transformation must be byte-for-byte identical to
  the subject_transformation of the entity it references, and the reference should carry
  nested type_mappings (and property_mappings where applicable). A mismatch does not raise
  an error - the relation is silently dropped.
- Omit subject_transformation and transformation when no expression is needed."""


class ZeroShotPromptStrategy(BasePromptStrategy):
    SAMPLE_RECORD_COUNT = 3

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
{SHARED_RULES}

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

        # Several records, not one: which columns vary per row and which repeat is the
        # main evidence for what identifies an entity, and a single row cannot show it.
        # Three costs +117 to +532 prompt tokens depending on the source.
        if schema.sample_records:
            samples = schema.sample_records[: self.SAMPLE_RECORD_COUNT]
            label = "SAMPLE RECORD" if len(samples) == 1 else "SAMPLE RECORDS"
            lines.append(f"\n{label}:")
            for i, sample in enumerate(samples, 1):
                if len(samples) > 1:
                    lines.append(f"  record {i}:")
                for k, v in sample.items():
                    lines.append(f"    {k}: {repr(v)[:100]}")

        return "\n".join(lines)
