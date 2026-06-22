from pathlib import Path

from rdflib import OWL, RDF, Graph, Namespace, URIRef
from rdflib.namespace import RDFS

from .models import OntologyClass, OntologyModel, OntologyProperty

NAMESPACE_STR = "https://thesis.tum.de/ontology#"
PREFIX = "thesis"
NAMESPACE = Namespace(NAMESPACE_STR)

class OntologyLoadError(Exception):
    pass


class OntologyLoader:

    def load(self, path: Path) -> OntologyModel:
        try:
            g = Graph()
            g.parse(path, format="turtle")

            classes = self._extract_classes(g)
            properties = self._extract_properties(g)

            return OntologyModel(
                classes=classes,
                properties=properties,
                prefix=PREFIX,
                namespace=NAMESPACE,
            )

        except OntologyLoadError:
            raise
        except Exception as e:
            raise OntologyLoadError(f"Failed to load ontology: {e}")

    def _extract_classes(self, g: Graph) -> list[OntologyClass]:
        classes = []
        for s in g.subjects(RDF.type, OWL.Class):
            if not isinstance(s, URIRef):
                continue
            label = g.value(s, RDFS.label)
            comment = g.value(s, RDFS.comment)
            subclass_of = [
                str(o) for o in g.objects(s, RDFS.subClassOf)
                if isinstance(o, URIRef)
            ]
            is_extension = str(g.value(s, NAMESPACE.isExtension)).lower() == "true"

            classes.append(OntologyClass(
                uri=str(s),
                label=str(label) if label else str(s).split("#")[-1],
                comment=str(comment) if comment else None,
                subclass_of=subclass_of,
                is_extension=is_extension,
            ))
        return classes

    def _extract_properties(self, g: Graph) -> list[OntologyProperty]:
        properties = []

        for rdf_type, is_object in [
            (OWL.ObjectProperty, True),
            (OWL.DatatypeProperty, False),
        ]:
            for s in g.subjects(RDF.type, rdf_type):
                if not isinstance(s, URIRef):
                    continue
                label = g.value(s, RDFS.label)
                comment = g.value(s, RDFS.comment)
                domain = [
                    str(o) for o in g.objects(s, RDFS.domain)
                    if isinstance(o, URIRef)
                ]
                range_ = [
                    str(o) for o in g.objects(s, RDFS.range)
                    if isinstance(o, URIRef)
                ]
                is_extension = str(g.value(s, NAMESPACE.isExtension)).lower() == "true"

                properties.append(OntologyProperty(
                    uri=str(s),
                    label=str(label) if label else str(s).split("#")[-1],
                    comment=str(comment) if comment else None,
                    domain=domain,
                    range_=range_,
                    is_object_property=is_object,
                    is_extension=is_extension,
                ))

        return properties