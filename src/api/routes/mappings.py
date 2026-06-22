import json
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from pipeline.mapping.models import MappingDocument

from ..deps import MAPPINGS_DIR, get_ontology_manager

router = APIRouter()


def _find_path(mapping_id: str) -> Path | None:
    for p in MAPPINGS_DIR.glob("*.json"):
        try:
            d = json.loads(p.read_text())
            if d.get("id") == mapping_id or p.stem == mapping_id:
                return p
        except Exception:
            pass
    return None


def _write(path: Path, doc: MappingDocument):
    path.write_text(json.dumps(doc.model_dump(), indent=2, default=str))


def _fill_defaults(body: dict) -> dict:
    body.setdefault("id", str(uuid.uuid4()))
    body.setdefault("generation_timestamp", datetime.now().isoformat())
    body.setdefault("llm_model", "manual")
    body.setdefault("strategy", "manual")
    body.setdefault("ontology_format", "manual")
    body.setdefault("include_descriptions", False)
    body.setdefault("prompt_tokens", 0)
    body.setdefault("completion_tokens", 0)
    body.setdefault("base_uri", "https://thesis.tum.de/baltic-sea-monitoring/instances/")
    body.setdefault("namespaces", {"bsm": "https://thesis.tum.de/baltic-sea-monitoring/ontology#"})
    body.setdefault("subject_mappings", [])
    body.setdefault("unmapped_fields", [])
    return body


@router.get("")
def list_mappings():
    result = []
    for p in sorted(MAPPINGS_DIR.glob("*.json")):
        try:
            d = json.loads(p.read_text())
            result.append({
                "id": d.get("id"),
                "filename": p.name,
                "source_name": d.get("source_name"),
                "status": d.get("status"),
                "generation_timestamp": d.get("generation_timestamp"),
                "llm_model": d.get("llm_model"),
                "strategy": d.get("strategy"),
            })
        except Exception:
            pass
    return result


# Must be defined before /{mapping_id} to avoid path conflict
@router.post("/validate")
def validate_mapping(body: dict):
    try:
        doc = MappingDocument.model_validate(body)
    except Exception as e:
        return {"valid": False, "errors": [str(e)], "warnings": []}

    manager = get_ontology_manager()
    class_uris = {c.uri for c in manager.ontology.classes}
    prop_uris = {p.uri for p in manager.ontology.properties}

    def resolve(uri: str) -> str:
        for prefix, ns in doc.namespaces.items():
            if uri.startswith(f"{prefix}:"):
                return ns + uri[len(f"{prefix}:"):]
        return uri

    errors: list[str] = []
    warnings: list[str] = []

    for i, sm in enumerate(doc.subject_mappings):
        if not sm.type_mappings:
            errors.append(f"Subject mapping {i}: no class assigned")
            continue
        for tm in sm.type_mappings:
            r = resolve(tm.class_uri)
            if r not in class_uris:
                warnings.append(f"Subject {i}: class '{tm.class_uri}' not found in ontology")
        if sm.subject.source == "column" and not sm.subject.column_name:
            errors.append(f"Subject {i}: subject source column not set")
        for pm in sm.property_mappings:
            r = resolve(pm.property_uri)
            if r not in prop_uris:
                warnings.append(f"Subject {i}: property '{pm.property_uri}' not in ontology")
            for val in pm.values:
                if val.value_source.source == "column" and not val.value_source.column_name:
                    warnings.append(f"Subject {i} / '{pm.property_uri}': source column not set")

    return {"valid": not errors, "errors": errors, "warnings": warnings}


@router.get("/{mapping_id}")
def get_mapping(mapping_id: str):
    p = _find_path(mapping_id)
    if not p:
        raise HTTPException(404, "Mapping not found")
    return json.loads(p.read_text())


@router.post("")
def create_mapping(body: dict):
    body = _fill_defaults(body)
    try:
        doc = MappingDocument.model_validate(body)
    except Exception as e:
        raise HTTPException(422, str(e))

    ts = doc.generation_timestamp.strftime("%Y%m%d_%H%M%S")
    filename = f"{doc.source_name}_manual_{ts}.json"
    path = MAPPINGS_DIR / filename
    _write(path, doc)
    return {"id": doc.id, "filename": filename}


@router.put("/{mapping_id}")
def update_mapping(mapping_id: str, body: dict):
    p = _find_path(mapping_id)
    if not p:
        raise HTTPException(404, "Mapping not found")
    body["id"] = mapping_id
    try:
        doc = MappingDocument.model_validate(body)
    except Exception as e:
        raise HTTPException(422, str(e))
    _write(p, doc)
    return {"id": doc.id, "filename": p.name}


@router.get("/{mapping_id}/export")
def export_mapping(mapping_id: str):
    p = _find_path(mapping_id)
    if not p:
        raise HTTPException(404, "Mapping not found")
    return Response(
        content=p.read_text(),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={p.name}"},
    )


@router.delete("/{mapping_id}")
def delete_mapping(mapping_id: str):
    p = _find_path(mapping_id)
    if not p:
        raise HTTPException(404, "Mapping not found")
    p.unlink()
    return {"deleted": True}
