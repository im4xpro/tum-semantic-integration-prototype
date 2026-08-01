from ..models import (
    FormattedOntology,
    OntologyClass,
    OntologyModel,
    OntologyProperty,
)
from .base import BaseFormatter


class CompactFormatter(BaseFormatter):
    def format(self, ontology: OntologyModel) -> FormattedOntology:
        ns = ontology.namespace
        px = ontology.prefix

        def to_compact(uri: str) -> str:
            return f"{px}:{uri[len(ns) :]}" if uri.startswith(ns) else uri

        class_uris = {cls.uri for cls in ontology.classes}
        subclass_map: dict[str, list[OntologyClass]] = {}
        for cls in ontology.classes:
            for parent_uri in cls.subclass_of:
                subclass_map.setdefault(parent_uri, []).append(cls)

        attached: set[str] = set()

        def format_property(prop: OntologyProperty, pad: str) -> str:
            kind = "obj" if prop.is_object_property else "data"
            desc = f" — {prop.comment}" if prop.comment else ""
            return f"{pad}    · {prop.label} ({kind}) [{to_compact(prop.uri)}]{desc}\n"

        def format_class(cls: OntologyClass, indent: int = 0) -> str:
            pad = "  " * indent
            ext = " [EXT]" if cls.is_extension else ""
            desc = f" — {cls.comment}" if cls.comment else ""
            result = f"{pad}- {cls.label} [{to_compact(cls.uri)}]{ext}{desc}\n"

            props = [p for p in ontology.properties if cls.uri in p.domain]
            # datatype properties first so they appear before object properties
            props.sort(key=lambda p: p.is_object_property)
            attached.update(p.uri for p in props)
            for prop in props:
                result += format_property(prop, pad)

            for subclass in subclass_map.get(cls.uri, []):
                result += format_class(subclass, indent + 1)
            return result

        # Roots are classes with no parent, plus any class whose declared parent the
        # ontology never declares as an owl:Class — without the second group such a
        # class is reachable from no root and would vanish from the rendering.
        top_level_classes = [
            cls
            for cls in ontology.classes
            if not cls.subclass_of or not any(p in class_uris for p in cls.subclass_of)
        ]
        content = "".join(format_class(cls) for cls in top_level_classes)

        # A property reaches no class when it declares no rdfs:domain, or when its
        # domain names something never declared as an owl:Class (three bsm:*Affiliation
        # properties currently do). Listing them keeps the rendering lossless.
        unattached = [p for p in ontology.properties if p.uri not in attached]
        if unattached:
            unattached.sort(key=lambda p: p.is_object_property)
            content += "- (unattached: no declared domain class)\n"
            content += "".join(format_property(p, "") for p in unattached)

        return FormattedOntology(
            format="compact",
            content=content,
            token_count=len(content) // 4,
        )
