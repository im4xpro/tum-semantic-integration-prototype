from pathlib import Path

from .formatters.class_list import ClassListFormatter
from .formatters.compact import CompactFormatter
from .formatters.json_ld import JsonLdFormatter
from .formatters.turtle import DefaultTurtleFormatter
from .models import FormattedOntology, OntologyClass, OntologyProperty
from .ontology_loader import OntologyLoader


class OntologyManager:
    def __init__(self, ontology_path: Path):
        self.ontology = OntologyLoader().load(ontology_path)

        self._class_index = {cls.uri: cls for cls in self.ontology.classes}
        self._property_index: dict[str, list[OntologyProperty]] = {}
        for prop in self.ontology.properties:
            for domain in prop.domain:
                if domain not in self._property_index:
                    self._property_index[domain] = []
                self._property_index[domain].append(prop)

        self._formatters = {
            "turtle": DefaultTurtleFormatter(ontology_path),
            "json_ld": JsonLdFormatter(ontology_path),
            "compact": CompactFormatter(),
            "class_list": ClassListFormatter(),
        }

    def get_formatted_ontology(self, format: str) -> FormattedOntology:
        formatter = self._formatters.get(format)
        if not formatter:
            raise ValueError(
                f"Unknown format: {format}. Choose from: {list(self._formatters.keys())}"
            )
        return formatter.format(self.ontology)

    def get_class(self, uri: str) -> OntologyClass | None:
        return self._class_index.get(uri)

    def get_properties_for_class(self, class_uri: str) -> list[OntologyProperty]:
        return self._property_index.get(class_uri, [])
