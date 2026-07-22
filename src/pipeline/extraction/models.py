import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ExtractedEntity(BaseModel):
    temp_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    subject_uri: str
    class_uri: str
    properties: dict[str, list[Any]] = {}  # multi-value: one list per predicate URI
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
