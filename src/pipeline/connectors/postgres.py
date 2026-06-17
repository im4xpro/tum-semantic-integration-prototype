from pydantic_settings import BaseSettings
import psycopg2
import psycopg2.extras
import datetime
from typing import Optional

from .models import ExtractedSchema, ColumnSchema
from .base import BaseConnector, ConnectorError


class PostgresConfig(BaseSettings):
    host: str
    port: int = 5432
    database: str
    user: str
    password: str
    table: str

    model_config = {"env_file": ".env", "env_prefix": "POSTGRES_", "extra": "ignore"}


class PostgresConnector(BaseConnector):

    def __init__(self, config: PostgresConfig):
        self.config = config
        self._conn: Optional[psycopg2.extensions.connection] = None

    def connect(self) -> None:
        try:
            self._conn = psycopg2.connect(
                host=self.config.host,
                port=self.config.port,
                dbname=self.config.database,
                user=self.config.user,
                password=self.config.password,
            )
        except Exception as e:
            raise ConnectorError(f"Failed to connect to PostgreSQL: {e}")

    def disconnect(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def extract_schema(self) -> ExtractedSchema:
        try:
            conn = self._conn
            if conn is None:
                raise ConnectorError("Not connected to PostgreSQL")

            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_name = %s
                    ORDER BY ordinal_position
                    """,
                    (self.config.table,),
                )
                columns = [
                    ColumnSchema(name=row[0], data_type=row[1])
                    for row in cur.fetchall()
                ]

            with conn.cursor(
                cursor_factory=psycopg2.extras.RealDictCursor
            ) as cur:
                cur.execute(f"SELECT * FROM {self.config.table} LIMIT 5")
                rows = cur.fetchall()

            sample_records = [
                {
                    k: str(v)
                    if not isinstance(v, (str, int, float, bool, type(None)))
                    else v
                    for k, v in dict(row).items()
                }
                for row in rows
            ]

            return ExtractedSchema(
                source_name=self.config.table,
                source_type="relational",
                columns=columns,
                inferred_fields=[],
                sample_records=sample_records,
                extraction_timestamp=datetime.datetime.now(),
            )

        except ConnectorError:
            raise
        except Exception as e:
            raise ConnectorError(f"Failed to extract schema: {e}")

    def fetch_records(self, limit: int) -> list[dict]:
        try:
            conn = self._conn
            if conn is None:
                raise ConnectorError("Not connected to PostgreSQL")

            with conn.cursor(
                cursor_factory=psycopg2.extras.RealDictCursor
            ) as cur:
                cur.execute(f"SELECT * FROM {self.config.table} LIMIT %s", (limit,))
                rows = cur.fetchall()

            return [
                {
                    k: str(v)
                    if not isinstance(v, (str, int, float, bool, type(None)))
                    else v
                    for k, v in dict(row).items()
                }
                for row in rows
            ]

        except Exception as e:
            raise ConnectorError(f"Failed to fetch records: {e}")