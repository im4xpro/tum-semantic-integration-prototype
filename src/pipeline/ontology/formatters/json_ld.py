import json
from pathlib import Path

from rdflib import Graph
from rdflib.compare import to_canonical_graph

from ..models import FormattedOntology, OntologyModel
from .base import BaseFormatter


class JsonLdFormatter(BaseFormatter):
    def __init__(self, ontology_path: Path):
        self.ontology_path = ontology_path

    def format(self, ontology: OntologyModel) -> FormattedOntology:
        source = Graph()
        source.parse(self.ontology_path, format="turtle")

        graph = Graph()
        for prefix, namespace in source.namespaces():
            graph.bind(prefix, namespace)
        for triple in to_canonical_graph(source):
            graph.add(triple)

        document = json.loads(
            graph.serialize(format="json-ld", auto_compact=True, indent=2)
        )
        document["@graph"].sort(key=lambda node: node.get("@id", ""))
        content = json.dumps(document, indent=2)

        return FormattedOntology(
            format="json_ld",
            content=content,
            token_count=len(content) // 4,
        )
