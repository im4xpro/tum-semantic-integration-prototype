from pathlib import Path

from ..models import FormattedOntology, OntologyModel
from .base import BaseFormatter


class DefaultTurtleFormatter(BaseFormatter):
    def __init__(self, ontology_path: Path):
        self.ontology_path = ontology_path

    def format(self, ontology: OntologyModel) -> FormattedOntology:
        content = self.ontology_path.read_text(encoding="utf-8")
        return FormattedOntology(
            format="turtle",
            content=content,
            token_count=len(content) // 4,
        )
