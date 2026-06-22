import json
from pathlib import Path

from pipeline.connectors.models import ExtractedSchema


def load_schema(source_name: str, schemas_dir: Path) -> ExtractedSchema:
    """Find the ExtractedSchema JSON for *source_name* under *schemas_dir*."""
    candidates = list(schemas_dir.glob("*.json"))
    for p in candidates:
        try:
            raw = json.loads(p.read_text())
            if raw.get("source_name") == source_name:
                return ExtractedSchema.model_validate(raw)
        except Exception:
            pass
    for p in candidates:
        if source_name in p.stem:
            return ExtractedSchema.model_validate(json.loads(p.read_text()))
    raise FileNotFoundError(
        f"No schema JSON found for source_name='{source_name}' in {schemas_dir}"
    )


def load_sample_records(source_name: str, schemas_dir: Path) -> list[dict]:
    """Return the sample_records stored in the schema JSON for *source_name*."""
    for p in schemas_dir.glob("*.json"):
        try:
            raw = json.loads(p.read_text())
            if raw.get("source_name") == source_name:
                return raw.get("sample_records", [])
        except Exception:
            pass
    raise FileNotFoundError(
        f"Schema not found for source '{source_name}' in {schemas_dir}"
    )
