from pathlib import Path

from rdflib import Graph

from ..models import FormattedOntology, OntologyModel
from .base import BaseFormatter


class JsonLdFormatter(BaseFormatter):
    def __init__(self, ontology_path: Path):
        self.ontology_path = ontology_path

    def format(self, ontology: OntologyModel) -> FormattedOntology:
        graph = Graph()
        graph.parse(self.ontology_path, format="turtle")
        content = graph.serialize(format="json-ld", auto_compact=True, indent=2)
        
        return FormattedOntology(
            format="json_ld",
            content=content,
            token_count=len(content) // 4,
        )
