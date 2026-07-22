import json

from ...connectors.models import ExtractedSchema
from ...ontology.manager import OntologyManager
from ...ontology.models import FormattedOntology
from .zero_shot import ZeroShotPromptStrategy

# A single static worked example in a generic "ex:" namespace, unrelated to the
# target ontology, so it teaches the JSON structure without hinting at answers.
# Deliberately includes a multi-value property, an IRI relation, and a subject
# whose identity is expression-only (no plain column value) so the model sees
# subject_transformation and the matching value transformation used together.
_EXAMPLE_SCHEMA = """  order_id: text
  customer_name: text
  customer_email: text
  total_amount: decimal"""

_EXAMPLE_MAPPING = {
    "subject_mappings": [
        {
            "subject": {"source": "column", "column_name": "order_id"},
            "subject_transformation": {"expression": "order_{order_id}"},
            "type_mappings": [{"class_uri": "ex:Order"}],
            "property_mappings": [
                {
                    "property_uri": "ex:totalAmount",
                    "values": [
                        {
                            "value_source": {
                                "source": "column",
                                "column_name": "total_amount",
                            },
                            "transformation": None,
                            "value_type": {
                                "type": "literal",
                                "type_mappings": [],
                                "property_mappings": [],
                            },
                        }
                    ],
                },
                {
                    "property_uri": "ex:placedBy",
                    "values": [
                        {
                            "value_source": {
                                "source": "column",
                                "column_name": "customer_email",
                            },
                            # Must match the Customer subject's own subject_transformation below,
                            # otherwise this relation will silently fail to resolve at extraction time.
                            "transformation": {"expression": "cust_{customer_email}"},
                            "value_type": {
                                "type": "iri",
                                "type_mappings": [{"class_uri": "ex:Customer"}],
                                "property_mappings": [],
                            },
                        }
                    ],
                },
            ],
        },
        {
            "subject": {"source": "column", "column_name": "customer_email"},
            "subject_transformation": {"expression": "cust_{customer_email}"},
            "type_mappings": [{"class_uri": "ex:Customer"}],
            "property_mappings": [
                {
                    "property_uri": "ex:name",
                    "values": [
                        {
                            "value_source": {
                                "source": "column",
                                "column_name": "customer_name",
                            },
                            "transformation": None,
                            "value_type": {
                                "type": "literal",
                                "type_mappings": [],
                                "property_mappings": [],
                            },
                        }
                    ],
                }
            ],
        },
    ],
    "unmapped_fields": [],
}


class FewShotPromptStrategy(ZeroShotPromptStrategy):
    def build_prompt(
        self,
        schema: ExtractedSchema,
        ontology: FormattedOntology,
        column_descriptions: dict[str, str] | None = None,
        ontology_manager: OntologyManager | None = None,
    ) -> tuple[str, str]:
        system_prompt, user_prompt = super().build_prompt(
            schema, ontology, column_descriptions, ontology_manager
        )
        example = f"""

EXAMPLE
Given this (unrelated) schema:
{_EXAMPLE_SCHEMA}

A correct mapping is:
{json.dumps(_EXAMPLE_MAPPING, indent=2)}

Notice how the IRI relation's transformation ("cust_{{customer_email}}") matches the
referenced subject's own subject_transformation exactly — this is how relations resolve."""

        return system_prompt + example, user_prompt
