from .base import BaseFormatter
from ..models import OntologyModel, FormattedOntology


class ClassListFormatter(BaseFormatter):

    def format(self, ontology: OntologyModel) -> FormattedOntology:
        lines = []

        for cls in ontology.classes:
            parts = [cls.label]

            if cls.subclass_of:
                parent_label = cls.subclass_of[0].split("#")[-1]
                parts.append(f"subClassOf: {parent_label}")

            props = [p for p in ontology.properties if cls.uri in p.domain]
            if props:
                prop_names = ", ".join(p.label for p in props[:8])
                parts.append(f"properties: {prop_names}")

            lines.append(" | ".join(parts))

        content = "\n".join(lines)

        return FormattedOntology(
            format="class_list",
            content=content,
            token_count=len(content) // 4,
        )