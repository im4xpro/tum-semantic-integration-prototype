#!/usr/bin/env python3
"""
Build data/schemas/marinetraffic_schema.json from a MarineTraffic API response.
"""

import argparse
import datetime
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR / "src"))

from pipeline.connectors.models import (
    ColumnSchema,
    ExtractedSchema,
)

SOURCE_NAME = "marinetraffic_vessels"
SCHEMA_PATH = BASE_DIR / "data" / "schemas" / "marinetraffic_schema.json"

_TYPES = {
    "lat": "double precision",
    "lon": "double precision",
    "speed": "double precision",
    "avg_speed": "double precision",
    "max_speed": "double precision",
    "width": "double precision",
    "heading": "integer",
    "course": "integer",
    "rot": "integer",
    "utc_seconds": "integer",
    "length": "integer",
    "grt": "integer",
    "dwt": "integer",
    "draught": "integer",
    "year_built": "integer",
    "l_fore": "integer",
    "w_left": "integer",
    "distance_to_go": "integer",
    "distance_travelled": "integer",
    "timestamp": "timestamp with time zone",
    "eta": "timestamp with time zone",
    "eta_calc": "timestamp with time zone",
    "eta_updated": "timestamp with time zone",
    "last_port_time": "timestamp with time zone",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "json_path", type=Path, help="MarineTraffic response (JSON array)"
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="keep at most N records"
    )
    args = parser.parse_args()

    payload = json.loads(args.json_path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):  # some endpoints wrap the array
        payload = payload.get("data", payload.get("DATA", []))
    if not payload:
        parser.error("no records in the payload")

    records = [{k.lower(): v for k, v in rec.items()} for rec in payload]
    if args.limit:
        records = records[: args.limit]

    names: list[str] = []
    for rec in records:
        names.extend(k for k in rec if k not in names)
    records = [{n: rec.get(n, "") for n in names} for rec in records]

    schema = ExtractedSchema(
        source_name=SOURCE_NAME,
        source_type="timeseries", # type: ignore
        columns=[
            ColumnSchema(name=n, data_type=_TYPES.get(n, "text"), is_nullable=True)
            for n in names
        ],
        inferred_fields=[],
        sample_records=records,
        extraction_timestamp=datetime.datetime.now(),
    )

    SCHEMA_PATH.write_text(
        json.dumps(schema.model_dump(), indent=4, default=str) + "\n", encoding="utf-8"
    )

    typed = [n for n in names if n in _TYPES]
    print(f"Read {len(payload)} record(s) from {args.json_path.name}")
    print(f"  columns          : {len(names)}")
    print(f"  typed non-text   : {len(typed)} -> {', '.join(typed)}")
    print(f"  sample_records   : {len(records)}")
    print(f"\nSchema written to {SCHEMA_PATH.relative_to(BASE_DIR)}")


if __name__ == "__main__":
    main()
