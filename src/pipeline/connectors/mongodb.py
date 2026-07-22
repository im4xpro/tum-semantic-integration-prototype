import datetime

import pymongo
from bson import ObjectId
from pydantic_settings import BaseSettings

from .base import BaseConnector, ConnectorError
from .models import ColumnSchema, ExtractedSchema


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
                    self._serialize(i)
                    if isinstance(i, dict)
                    else str(i)
                    if isinstance(i, ObjectId)
                    else i
                    for i in v
                ]
            else:
                result[k] = v
        return result

    def extract_schema(self) -> ExtractedSchema:
        try:
            if self._collection is None:
                raise ConnectorError("Not connected to MongoDB")

            samples = list(self._collection.aggregate([{"$sample": {"size": 50}}]))

            schema_properties: dict[str, set] = {}
            for doc in samples:
                schema_type = doc.get("schema", "Unknown")
                props = doc.get("properties", {})

                if schema_type not in schema_properties:
                    schema_properties[schema_type] = set()

                if isinstance(props, dict):
                    for key in props.keys():
                        schema_properties[schema_type].add(key)

            inferred_fields = [
                ColumnSchema(name=f"{schema_type}.{field}", data_type="list")
                for schema_type, fields in schema_properties.items()
                for field in sorted(fields)
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
            if self._collection is None:
                raise ConnectorError("Not connected to MongoDB")

            docs = self._collection.find({}, limit=limit)
            return [self._serialize(doc) for doc in docs]
        except Exception as e:
            raise ConnectorError(f"Failed to fetch records: {e}")
