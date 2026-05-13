from .models import OntologyModel


class ValidationResult:
    def __init__(
        self,
        is_valid: bool,
        unknown_classes: list[str],
        unknown_properties: list[str],
    ):
        self.is_valid = is_valid
        self.unknown_classes = unknown_classes
        self.unknown_properties = unknown_properties


class OntologyValidator:

    def __init__(self, ontology: OntologyModel):
        self.ontology = ontology
        self._class_uris = {cls.uri for cls in ontology.classes}
        self._property_uris = {prop.uri for prop in ontology.properties}

    def validate_class(self, class_uri: str) -> bool:
        raise NotImplementedError

    def validate_property(self, property_uri: str) -> bool:
        raise NotImplementedError

    def validate_mapping(self, mapping: dict) -> ValidationResult:
        raise NotImplementedError