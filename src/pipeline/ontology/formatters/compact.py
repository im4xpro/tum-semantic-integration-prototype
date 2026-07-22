from ..models import FormattedOntology, OntologyClass, OntologyModel
from .base import BaseFormatter


class CompactFormatter(BaseFormatter):
    def format(self, ontology: OntologyModel) -> FormattedOntology:
        ns = ontology.namespace
        px = ontology.prefix

        def to_compact(uri: str) -> str:
            return f"{px}:{uri[len(ns) :]}" if uri.startswith(ns) else uri

        subclass_map: dict[str, list[OntologyClass]] = {}
        for cls in ontology.classes:
            for parent_uri in cls.subclass_of:
                subclass_map.setdefault(parent_uri, []).append(cls)

        def format_class(cls: OntologyClass, indent: int = 0) -> str:
            pad = "  " * indent
            ext = " [EXT]" if cls.is_extension else ""
            desc = f" — {cls.comment}" if cls.comment else ""
            result = f"{pad}- {cls.label} [{to_compact(cls.uri)}]{ext}{desc}\n"

            props = [p for p in ontology.properties if cls.uri in p.domain]
            # datatype properties first so they appear before object properties
            props.sort(key=lambda p: p.is_object_property)
            for prop in props:
                kind = "obj" if prop.is_object_property else "data"
                desc = f" — {prop.comment}" if prop.comment else ""
                result += (
                    f"{pad}    · {prop.label} ({kind}) [{to_compact(prop.uri)}]{desc}\n"
                )

            for subclass in subclass_map.get(cls.uri, []):
                result += format_class(subclass, indent + 1)
            return result

        top_level_classes = [cls for cls in ontology.classes if not cls.subclass_of]
        content = "".join(format_class(cls) for cls in top_level_classes)

        return FormattedOntology(
            format="compact",
            content=content,
            token_count=len(content) // 4,
        )
