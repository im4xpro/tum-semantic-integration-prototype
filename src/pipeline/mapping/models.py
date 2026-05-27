from pydantic import BaseModel, Field
from typing import Literal
from datetime import datetime
import uuid

from pipeline.mapping.llm_clients.factory import LLMProvider

class PropertySource(BaseModel):
    source: Literal["column", "constant"]
    column_name: str | None = None
    constant_value: str | None = None

class CodeTransformation(BaseModel):
    expression: str
    language: Literal["python"] = "python"

class TypeMapping(BaseModel):
    class_uri: str

class ValueType(BaseModel):
    value_type: Literal["literal", "uri"]
    type_mappings: list[TypeMapping] = []
    property_mappings: list["PropertyMapping"] = []

class ValueDefinition(BaseModel):
    value_source: PropertySource
    transformation: CodeTransformation | None = None
    value_type: ValueType
    
class PropertyMapping(BaseModel):
    property_uri: str
    values: list[ValueDefinition]

ValueType.model_rebuild()

class SubjectMapping(BaseModel):
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
    rag_enabled: bool
    base_uri: str = "https://thesis.tum.de/baltic-sea-monitoring/instances/"
    namespaces: dict[str, str] = {
        "bsm": "https://thesis.tum.de/baltic-sea-monitoring/ontology#"
    }
    subject_mappings: list[SubjectMapping]
    unmapped_fields: list[str] = []
    generation_timestamp: datetime
    prompt_tokens: int
    completion_tokens: int
    status: Literal["draft", "approved", "superseded", "rejected"] = "draft"
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    superseded_by: str | None = None  # ID of the newer mapping

# TODO: Adjust the configuration if needed, maybe make it more flexible
class MappingConfig(BaseModel):
    provider: LLMProvider
    llm_model: str
    strategy: Literal["zero_shot", "few_shot", "chain_of_thought", "schema_guided"]
    ontology_format: Literal["turtle", "compact", "class_list"]
    rag_enabled: bool
    temperature: float = 0.0