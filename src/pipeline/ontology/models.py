from pydantic import BaseModel


class OntologyClass(BaseModel):
    uri: str
    label: str
    comment: str | None = None
    subclass_of: list[str] = []
    is_extension: bool = False

class OntologyProperty(BaseModel):
    uri: str
    label: str
    comment: str | None = None
    domain: list[str] = []
    range_: list[str] = []
    is_object_property: bool = False
    is_extension: bool = False

class OntologyModel(BaseModel):
    classes: list[OntologyClass] = []
    properties: list[OntologyProperty] = []
    prefix: str
    namespace: str

class FormattedOntology(BaseModel):
    format: str
    content: str
    token_count: int