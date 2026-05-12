from pydantic import BaseModel
from typing import Literal
import datetime

class ColumnSchema(BaseModel):
    name: str
    data_type: str
    is_primary_key: bool = False
    is_nullable: bool = True
    
class ExtractedSchema(BaseModel):
    source_name: str
    source_type: Literal["relational", "document", "timeseries", "stream"]
    columns: list[ColumnSchema]
    inferred_fields: list[ColumnSchema]
    sample_records: list[dict]
    extraction_timestamp: datetime.datetime
    