import json
from pathlib import Path

from pipeline.connectors.base import BaseConnector
from pipeline.connectors.models import ExtractedSchema


class SchemaExtractor:
    def __init__(self, connector: BaseConnector):
        self.connector = connector

    def extract_schema(self) -> ExtractedSchema:
        return self.connector.extract_schema()

    def save_schema(self, schema: ExtractedSchema, path: Path) -> None:
        with open(path, "w") as f:
            json.dump(schema.model_dump(), f, indent=4, default=str)

    def load_schema(self, path: Path) -> ExtractedSchema:
        with open(path, "r") as f:
            data = json.load(f)
            return ExtractedSchema.model_validate(data)
