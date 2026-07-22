from pathlib import Path

from rdflib import OWL, RDF, Graph, URIRef
from rdflib.namespace import RDFS

from .models import OntologyClass, OntologyModel, OntologyProperty


class OntologyLoadError(Exception):
    pass


class OntologyLoader:
    def load(self, path: Path) -> OntologyModel:
        try:
            g = Graph()
            g.parse(path, format="turtle")

            prefix, namespace_str = self._detect_namespace(g)

            ext_prop = URIRef(f"{namespace_str}isExtension")
            classes = self._extract_classes(g, ext_prop)
            properties = self._extract_properties(g, ext_prop)

            return OntologyModel(
                classes=classes,
                properties=properties,
                prefix=prefix,
                namespace=namespace_str,
            )

        except OntologyLoadError:
            raise
        except Exception as e:
            raise OntologyLoadError(f"Failed to load ontology: {e}")

    def _detect_namespace(self, g: Graph) -> tuple[str, str]:
        # Uses the namespace with the most owl:Class definitions so that
        # imported/referenced external namespaces don't win by accident.
        ns_counts: dict[str, int] = {}
        for s in g.subjects(RDF.type, OWL.Class):
            if isinstance(s, URIRef):
                s_str = str(s)
                for ns in (str(n) for _, n in g.namespaces()):
                    if len(ns) > 10 and s_str.startswith(ns):
                        ns_counts[ns] = ns_counts.get(ns, 0) + 1

        if not ns_counts:
            raise OntologyLoadError("Could not detect ontology namespace")

        best_ns = max(ns_counts, key=lambda n: ns_counts[n])
        for px, ns in g.namespaces():
            if str(ns) == best_ns:
                return str(px), best_ns
        return "ont", best_ns

    def _get_label(self, g: Graph, s: URIRef) -> str:
        label = g.value(s, RDFS.label)
        return str(label) if label else str(s).split("#")[-1]

    def _get_comment(self, g: Graph, s: URIRef) -> str | None:
        comment = g.value(s, RDFS.comment)
        return str(comment) if comment else None

    def _is_extension(self, g: Graph, s: URIRef, ext_prop: URIRef) -> bool:
        return str(g.value(s, ext_prop)).lower() == "true"

    def _extract_classes(self, g: Graph, ext_prop: URIRef) -> list[OntologyClass]:
        classes = []
        for s in g.subjects(RDF.type, OWL.Class):
            if not isinstance(s, URIRef):
                continue
            subclass_of = [
                str(o) for o in g.objects(s, RDFS.subClassOf) if isinstance(o, URIRef)
            ]
            classes.append(
                OntologyClass(
                    uri=str(s),
                    label=self._get_label(g, s),
                    comment=self._get_comment(g, s),
                    subclass_of=subclass_of,
                    is_extension=self._is_extension(g, s, ext_prop),
                )
            )
        return classes

    def _extract_properties(self, g: Graph, ext_prop: URIRef) -> list[OntologyProperty]:
        properties = []
        for rdf_type, is_object in [
            (OWL.ObjectProperty, True),
            (OWL.DatatypeProperty, False),
        ]:
            for s in g.subjects(RDF.type, rdf_type):
                if not isinstance(s, URIRef):
                    continue
                domain = [
                    str(o) for o in g.objects(s, RDFS.domain) if isinstance(o, URIRef)
                ]
                range_ = [
                    str(o) for o in g.objects(s, RDFS.range) if isinstance(o, URIRef)
                ]
                properties.append(
                    OntologyProperty(
                        uri=str(s),
                        label=self._get_label(g, s),
                        comment=self._get_comment(g, s),
                        domain=domain,
                        range_=range_,
                        is_object_property=is_object,
                        is_extension=self._is_extension(g, s, ext_prop),
                    )
                )
        return properties
