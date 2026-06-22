import datetime
from typing import Literal

from pydantic import BaseModel


class ColumnSchema(BaseModel):
    name: str
    data_type: str
    is_primary_key: bool = False
    is_nullable: bool = True

class ExtractedSchema(BaseModel):
    source_name: str
    source_type: Literal["relational", "document", "timeseries", "stream"]
    columns: list[ColumnSchema]
    inferred_fields: list[ColumnSchema] # Used for fields not explicitly in the source schema but inferred from data entries
    sample_records: list[dict]
    extraction_timestamp: datetime.datetime
