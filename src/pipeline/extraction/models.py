from pydantic import BaseModel, Field
from datetime import datetime
from typing import Any
import uuid


class ExtractedEntity(BaseModel):
    temp_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    class_uri: str
    properties: dict[str, Any] = {}
    source_name: str
    source_record_id: str


class ExtractedRelation(BaseModel):
    subject_temp_id: str
    predicate_uri: str
    object_temp_id: str


class ExtractionResult(BaseModel):
    source_record: dict
    entities: list[ExtractedEntity] = []
    relations: list[ExtractedRelation] = []
    extraction_timestamp: datetime = Field(default_factory=datetime.now)
    mapping_path: str