import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from pipeline.mapping.llm_clients.factory import LLMProvider


class PropertySource(BaseModel):
    source: Literal["column", "constant", "row_index"]
    column_name: str | None = None
    constant_value: str | None = None


class CodeTransformation(BaseModel):
    expression: str
    language: Literal["python"] = "python"


class TypeMapping(BaseModel):
    class_uri: str


class ValueType(BaseModel):
    type: Literal["literal", "iri"]
    type_mappings: list[TypeMapping] = []
    property_mappings: list["PropertyMapping"] = []


class ValueDefinition(BaseModel):
    value_source: PropertySource
    transformation: CodeTransformation | None = None
    value_type: ValueType = Field(default_factory=lambda: ValueType(type="literal"))


class PropertyMapping(BaseModel):
    property_uri: str
    values: list[ValueDefinition]


ValueType.model_rebuild()


class SubjectMapping(BaseModel):
    label: str | None = None
    subject: PropertySource
    subject_transformation: CodeTransformation | None = None
    type_mappings: list[TypeMapping] = []
    property_mappings: list[PropertyMapping] = []


class MappingDocument(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_name: str
    llm_model: str
    strategy: str
    ontology_format: str
    include_descriptions: bool
    base_uri: str = "https://thesis.tum.de/baltic-sea-monitoring/instances/"
    namespaces: dict[str, str] = {
        "bsm": "https://thesis.tum.de/baltic-sea-monitoring/ontology#"
    }
    subject_mappings: list[SubjectMapping]
    unmapped_fields: list[str] = []
    generation_timestamp: datetime
    prompt_tokens: int
    completion_tokens: int


class MappingConfig(BaseModel):
    provider: LLMProvider
    llm_model: str
    strategy: Literal["zero_shot", "few_shot", "chain_of_thought"]
    ontology_format: Literal["turtle", "compact", "class_list"]
    include_descriptions: bool
    temperature: float = 0.0
