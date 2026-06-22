import json

from ...connectors.models import ExtractedSchema
from ...ontology.manager import OntologyManager
from ...ontology.models import FormattedOntology
from .zero_shot import OUTPUT_SCHEMA, ZeroShotPromptStrategy


class ChainOfThoughtPromptStrategy(ZeroShotPromptStrategy):
    """
    Same task as zero-shot, but instructed to reason in prose before emitting
    JSON. Unlike zero-shot, the response is not pure JSON, so
    MappingGenerator._parse_json() must extract the trailing JSON block.
    """

    def build_prompt(
        self,
        schema: ExtractedSchema,
        ontology: FormattedOntology,
        column_descriptions: dict[str, str] | None = None,
        ontology_manager: OntologyManager | None = None,
    ) -> tuple[str, str]:
        system_prompt = f"""You are a semantic data integration expert.
Your task is to map a data source schema to an OWL ontology using an RML-style subject-centric structure.

First, think step by step in plain text:
- List the distinct entity types present in the schema (e.g. one column group per real-world entity).
- For each entity type, decide which column or constant value is its identifier (the subject).
- For each entity type, decide which ontology class it corresponds to.
- For each remaining column, decide which ontology property it maps to, and whether its value is a literal or a reference (IRI) to another entity.
- Note any columns that have no suitable ontology match.

After your reasoning, output the final mapping as a JSON code block (```json ... ```) matching this exact structure, and nothing after it:
{json.dumps(OUTPUT_SCHEMA, indent=2)}

Omit subject_transformation and transformation when no expression is needed."""

        schema_description = self._format_schema(schema, column_descriptions)

        user_prompt = f"""Map the following data source schema to the ontology.

DATA SOURCE: {schema.source_name} (type: {schema.source_type})

SCHEMA:
{schema_description}

ONTOLOGY:
{ontology.content}

Think step by step, then return the mapping as a JSON code block."""

        return system_prompt, user_prompt
