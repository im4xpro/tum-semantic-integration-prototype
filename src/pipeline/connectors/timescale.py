from .postgres import PostgresConnector, PostgresConfig
from .models import ExtractedSchema
from pydantic_settings import BaseSettings


class TimescaleConfig(BaseSettings):
    host: str
    port: int = 5433
    database: str
    user: str
    password: str
    table: str

    model_config = {"env_file": ".env", "env_prefix": "TIMESCALE_", "extra": "ignore"}


class TimescaleConnector(PostgresConnector):

    def __init__(self, config: TimescaleConfig):
        self.config = config
        self._conn = None

    def extract_schema(self) -> ExtractedSchema:
        schema = super().extract_schema()
        return schema.model_copy(update={"source_type": "timeseries"})