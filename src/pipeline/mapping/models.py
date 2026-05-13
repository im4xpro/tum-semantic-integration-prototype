from pydantic import BaseModel, Field
from typing import Literal
from datetime import datetime
import uuid

from pipeline.mapping.llm_clients.factory import LLMProvider


class FieldMapping(BaseModel):
    source_field: str
    target_class: str
    target_property: str
    confidence: float
    reasoning: str
    is_entity_creating: bool
    unmapped: bool = False

class RelationMapping(BaseModel):
    subject_field: str
    predicate: str
    object_field: str
    reasoning: str

# TODO: Adjust the configuration if needed, maybe make it more flexible
class MappingConfig(BaseModel):
    provider: LLMProvider
    llm_model: str
    strategy: Literal["zero_shot", "few_shot", "chain_of_thought", "schema_guided"]
    ontology_format: Literal["turtle", "compact", "class_list"]
    rag_enabled: bool
    temperature: float = 0.0

# Generated mapping with metadata for audit trail and versioning, will be stored in the database
class GeneratedMapping(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_name: str
    llm_model: str
    strategy: str
    ontology_format: str
    rag_enabled: bool
    field_mappings: list[FieldMapping]
    relation_mappings: list[RelationMapping]
    unmapped_fields: list[str] = []
    generation_timestamp: datetime
    prompt_tokens: int
    completion_tokens: int
    status: Literal["draft", "approved", "superseded", "rejected"] = "draft"
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    superseded_by: str | None = None  # ID of the newer mapping