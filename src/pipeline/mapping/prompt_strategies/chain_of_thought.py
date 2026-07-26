import json

from ...connectors.models import ExtractedSchema
from ...ontology.manager import OntologyManager
from ...ontology.models import FormattedOntology
from .zero_shot import OUTPUT_SCHEMA, ZeroShotPromptStrategy


class ChainOfThoughtPromptStrategy(ZeroShotPromptStrategy):
    # Unlike zero-shot, the response is not pure JSON — MappingGenerator._parse_json()
    # must extract the trailing ```json block from the prose reasoning.

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
- For each subject and property decision, note your confidence (0.0-1.0), the single best evidence category (basis: name, description, value, structural, or weak), and a concrete one-line justification citing the actual name, description, or values — not generic filler.
- Note any columns that have no suitable ontology match.

After your reasoning, output the final mapping as a JSON code block (```json ... ```) matching this exact structure, and nothing after it:
{json.dumps(OUTPUT_SCHEMA, indent=2)}

Omit subject_transformation and transformation when no expression is needed."""

        _, user_prompt = super().build_prompt(
            schema, ontology, column_descriptions, ontology_manager
        )
        return system_prompt, user_prompt

    def _closing_instruction(self) -> str:
        return "Think step by step, then return the mapping as a JSON code block."
