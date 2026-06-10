import json

from fastapi import APIRouter, HTTPException

from ..deps import SCHEMAS_DIR

router = APIRouter()


@router.get("")
def list_schemas():
    result = []
    for path in sorted(SCHEMAS_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text())
            result.append({
                "source_name": data.get("source_name"),
                "source_type": data.get("source_type"),
                "column_count": len(data.get("columns", [])),
                "filename": path.name,
            })
        except Exception:
            pass
    return result


@router.get("/{source_name}")
def get_schema(source_name: str):
    for path in SCHEMAS_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text())
            if data.get("source_name") == source_name:
                return data
        except Exception:
            pass
    raise HTTPException(404, f"Schema '{source_name}' not found")
