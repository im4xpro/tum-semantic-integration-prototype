from pathlib import Path
from .base import BaseFormatter
from ..models import OntologyModel, FormattedOntology, OntologyClass


class CompactFormatter(BaseFormatter):

    def format(self, ontology: OntologyModel) -> FormattedOntology:
        subclass_map: dict[str, list[OntologyClass]] = {}
        for cls in ontology.classes:
            for parent_uri in cls.subclass_of:
                if parent_uri not in subclass_map:
                    subclass_map[parent_uri] = []
                subclass_map[parent_uri].append(cls)

        def format_class(cls: OntologyClass, indent: int = 0) -> str:
            prefix = "  " * indent
            result = f"{prefix}- {cls.label}"
            if cls.is_extension:
                result += " [EXT]"
            result += "\n"

            props = [p for p in ontology.properties if cls.uri in p.domain]
            for prop in props[:5]:
                prop_marker = "obj" if prop.is_object_property else "data"
                result += f"{prefix}    · {prop.label} ({prop_marker})\n"

            for subclass in subclass_map.get(cls.uri, []):
                result += format_class(subclass, indent + 1)
            return result

        top_level_classes = [cls for cls in ontology.classes if not cls.subclass_of]
        content = ""
        for cls in top_level_classes:
            content += format_class(cls)

        return FormattedOntology(
            format="compact",
            content=content,
            token_count=len(content) // 4,
        )