from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import pymongo
import datetime
from bson import ObjectId

from .model import ExtractedSchema, ColumnSchema
from .base import BaseConnector, ConnectorError


class MongoDBConfig(BaseSettings):
    uri: str
    database: str
    collection: str

    model_config = {"env_file": ".env", "env_prefix": "MONGODB_", "extra": "ignore"}


class MongoDBConnector(BaseConnector):

    def __init__(self, config: MongoDBConfig):
        self.config = config
        self._client = None
        self._db = None
        self._collection = None

    def connect(self) -> None:
        try:
            self._client = pymongo.MongoClient(self.config.uri)
            self._db = self._client[self.config.database]
            self._collection = self._db[self.config.collection]
        except Exception as e:
            raise ConnectorError(f"Failed to connect to MongoDB: {e}")

    def disconnect(self) -> None:
        if self._client:
            self._client.close()
            self._client = None
            self._db = None
            self._collection = None

    def _serialize(self, doc: dict) -> dict:
        result = {}
        for k, v in doc.items():
            if isinstance(v, ObjectId):
                result[k] = str(v)
            elif isinstance(v, dict):
                result[k] = self._serialize(v)
            elif isinstance(v, list):
                result[k] = [
                    self._serialize(i) if isinstance(i, dict)
                    else str(i) if isinstance(i, ObjectId)
                    else i
                    for i in v
                ]
            else:
                result[k] = v
        return result

    def extract_schema(self) -> ExtractedSchema:
        try:
            samples = list(self._collection.aggregate([
                {"$sample": {"size": 50}}
            ]))

            all_fields: dict[str, str] = {}
            for doc in samples:
                for key, value in doc.items():
                    if key not in all_fields:
                        all_fields[key] = type(value).__name__

            inferred_fields = [
                ColumnSchema(name=k, data_type=v)
                for k, v in all_fields.items()
            ]

            sample_records = [self._serialize(doc) for doc in samples[:5]]

            return ExtractedSchema(
                source_name=self.config.collection,
                source_type="document",
                columns=[],
                inferred_fields=inferred_fields,
                sample_records=sample_records,
                extraction_timestamp=datetime.datetime.now(),
            )

        except ConnectorError:
            raise
        except Exception as e:
            raise ConnectorError(f"Failed to extract schema: {e}")

    def fetch_records(self, limit: int) -> list[dict]:
        try:
            docs = self._collection.find({}, limit=limit)
            return [self._serialize(doc) for doc in docs]
        except Exception as e:
            raise ConnectorError(f"Failed to fetch records: {e}")