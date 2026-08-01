from ..models import FormattedOntology, OntologyModel, OntologyProperty
from .base import BaseFormatter


class ClassListFormatter(BaseFormatter):
    """One flat line per class: term, parent, and every property split by kind.

    This is the terse end of the prompt-format ladder. It carries the same terms
    as the compact formatter and drops only rdfs:comment and the indented
    hierarchy, so the two formats differ in verbosity rather than in coverage —
    otherwise an experiment varying the format would confound presentation with
    how much of the ontology the model was shown at all.
    """

    def format(self, ontology: OntologyModel) -> FormattedOntology:
        ns = ontology.namespace
        px = ontology.prefix

        def to_compact(uri: str) -> str:
            return f"{px}:{uri[len(ns) :]}" if uri.startswith(ns) else uri

        def term(label: str, uri: str) -> str:
            # The URI is what the model has to emit in a mapping, so it is spelled
            # out for every term rather than left to be guessed from the label.
            return f"{label} [{to_compact(uri)}]"

        def property_groups(props: list[OntologyProperty]) -> list[str]:
            # Grouped by kind (datatype first, as in the compact formatter) so the
            # literal/reference distinction survives without a marker per property.
            datatype = [p for p in props if not p.is_object_property]
            obj = [p for p in props if p.is_object_property]
            groups = []
            if datatype:
                groups.append(
                    "data: " + ", ".join(term(p.label, p.uri) for p in datatype)
                )
            if obj:
                groups.append("obj: " + ", ".join(term(p.label, p.uri) for p in obj))
            return groups

        class_by_uri = {cls.uri: cls for cls in ontology.classes}
        attached: set[str] = set()
        lines = []

        for cls in ontology.classes:
            parts = [term(cls.label, cls.uri)]

            for parent_uri in cls.subclass_of:
                parent = class_by_uri.get(parent_uri)
                # Render the parent exactly as its own line does, so the hierarchy
                # can be resolved by string match. (Naming the class by its label
                # but its parent by the URI local name left the two inconsistent:
                # "Battlespace Concept" vs "subClassOf: BattlespaceConcept".)
                parts.append(
                    "subClassOf: "
                    + (
                        term(parent.label, parent.uri)
                        if parent
                        else to_compact(parent_uri)
                    )
                )

            props = [p for p in ontology.properties if cls.uri in p.domain]
            attached.update(p.uri for p in props)
            parts.extend(property_groups(props))

            lines.append(" | ".join(parts))

        # A property reaches no class line when it declares no rdfs:domain, or when
        # its domain names something the ontology never declares as an owl:Class
        # (bsm:GeopoliticalAffiliation and two siblings currently do this). Listing
        # them keeps the rendering lossless and surfaces the dangling domains rather
        # than silently dropping the properties, as the compact formatter still does.
        unattached = [p for p in ontology.properties if p.uri not in attached]
        if unattached:
            lines.append(
                " | ".join(
                    [
                        "(unattached: no declared domain class)",
                        *property_groups(unattached),
                    ],
                )
            )

        content = "\n".join(lines)

        return FormattedOntology(
            format="class_list",
            content=content,
            token_count=len(content) // 4,
        )
