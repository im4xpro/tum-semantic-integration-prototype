"""
Mappings API — CRUD over stored mappings, plus stateless LLM generation.

Endpoints
---------
GET    /api/mappings                 List stored mappings
POST   /api/mappings/validate        Validate a mapping against the ontology
POST   /api/mappings/generate        Generate a mapping suggestion via LLM (no side effects)
GET    /api/mappings/{id}            Get one stored mapping
POST   /api/mappings                 Create/save a mapping
PUT    /api/mappings/{id}            Update a stored mapping
GET    /api/mappings/{id}/prompt     Exact system/user prompt sent to the LLM
GET    /api/mappings/{id}/response   Exact raw LLM response, before JSON parsing
GET    /api/mappings/{id}/export     Download a mapping as a JSON attachment
DELETE /api/mappings/{id}            Delete a stored mapping
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel

from pipeline.connectors.models import ColumnSchema, ExtractedSchema
from pipeline.mapping.llm_clients.factory import LLMProvider
from pipeline.mapping.mapping_generator import MappingGenerator, MappingGeneratorError
from pipeline.mapping.models import MappingConfig, MappingDocument

from ..deps import MAPPINGS_DIR, get_ontology_manager

router = APIRouter()


class GenerateMappingSchema(BaseModel):
    """Source schema as sent by an interactive caller (e.g. the visual editor).

    Deliberately looser than pipeline.connectors.models.ExtractedSchema: no
    extraction_timestamp, and source_type is a free string (the editor allows
    arbitrary types like "csv"/"json"/"manual", not just the connector Literal)."""

    source_name: str
    source_type: str
    columns: list[ColumnSchema]
    inferred_fields: list[ColumnSchema] = []
    sample_records: list[dict] = []


class GenerateMappingRequest(BaseModel):
    # `source_schema`, not `schema`: a field named `schema` shadows BaseModel.schema()
    # and raises a Pydantic warning. Callers send the payload under this key.
    source_schema: GenerateMappingSchema
    strategy: Literal["zero_shot", "few_shot", "chain_of_thought"]
    provider: LLMProvider
    llm_model: str
    ontology_format: Literal["turtle", "json_ld", "compact", "class_list"]
    include_descriptions: bool = False
    column_descriptions: dict[str, str] | None = None
    temperature: float = 0.0


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
    body.setdefault(
        "base_uri", "https://thesis.tum.de/baltic-sea-monitoring/instances/"
    )
    body.setdefault(
        "namespaces", {"bsm": "https://thesis.tum.de/baltic-sea-monitoring/ontology#"}
    )
    body.setdefault("subject_mappings", [])
    body.setdefault("unmapped_fields", [])
    return body


@router.get("")
def list_mappings():
    result = []
    for p in sorted(MAPPINGS_DIR.glob("*.json")):
        try:
            d = json.loads(p.read_text())
            result.append(
                {
                    "id": d.get("id"),
                    "filename": p.name,
                    "source_name": d.get("source_name"),
                    "generation_timestamp": d.get("generation_timestamp"),
                    "llm_model": d.get("llm_model"),
                    "strategy": d.get("strategy"),
                }
            )
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
                return ns + uri[len(f"{prefix}:") :]
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
                warnings.append(
                    f"Subject {i}: class '{tm.class_uri}' not found in ontology"
                )
        if sm.subject.source == "column" and not sm.subject.column_name:
            errors.append(f"Subject {i}: subject source column not set")
        for pm in sm.property_mappings:
            r = resolve(pm.property_uri)
            if r not in prop_uris:
                warnings.append(
                    f"Subject {i}: property '{pm.property_uri}' not in ontology"
                )
            for val in pm.values:
                if (
                    val.value_source.source == "column"
                    and not val.value_source.column_name
                ):
                    warnings.append(
                        f"Subject {i} / '{pm.property_uri}': source column not set"
                    )

    return {"valid": not errors, "errors": errors, "warnings": warnings}


# Defined before /{mapping_id} to avoid the path colliding with a mapping id.
@router.post("/generate", response_model=MappingDocument)
def generate_mapping(req: GenerateMappingRequest) -> MappingDocument:
    """Generate a mapping suggestion from an LLM and return it directly, with no
    side effects: nothing is extracted, uploaded to a triple store, or persisted to
    data/mappings/. Persisting is the caller's job, only after a human reviews the
    suggestion (REQ-HITL-FR-02) — keeping generation inert also keeps the benchmark
    corpus in data/mappings/ free of ad-hoc interactive suggestions."""
    # model_construct (not ExtractedSchema(...)) so an interactive caller can pass a
    # source_type outside the connectors' Literal (e.g. "csv"): every field here is
    # already validated via GenerateMappingSchema/ColumnSchema, and generation only
    # ever string-interpolates source_type into the prompt.
    schema = ExtractedSchema.model_construct(
        source_name=req.source_schema.source_name,
        source_type=req.source_schema.source_type,
        columns=req.source_schema.columns,
        inferred_fields=req.source_schema.inferred_fields,
        sample_records=req.source_schema.sample_records,
        extraction_timestamp=datetime.now(),
    )
    config = MappingConfig(
        provider=req.provider,
        llm_model=req.llm_model,
        strategy=req.strategy,
        ontology_format=req.ontology_format,
        include_descriptions=req.include_descriptions,
        temperature=req.temperature,
    )
    try:
        return MappingGenerator(config).generate(
            schema, get_ontology_manager(), req.column_descriptions
        )
    except MappingGeneratorError as e:
        # The LLM returned something unparseable — an upstream problem, not a bug here.
        raise HTTPException(502, str(e)) from e


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


@router.get("/{mapping_id}/prompt", response_class=PlainTextResponse)
def get_mapping_prompt(mapping_id: str):
    """The exact system/user prompt sent to the LLM — empty for mappings that
    weren't LLM-generated (e.g. the manually-authored gold mapping)."""
    p = _find_path(mapping_id)
    if not p:
        raise HTTPException(404, "Mapping not found")
    d = json.loads(p.read_text())
    system_prompt = d.get("system_prompt")
    user_prompt = d.get("user_prompt")
    if not system_prompt and not user_prompt:
        return PlainTextResponse(
            "No prompt recorded for this mapping (not LLM-generated, "
            "or generated before prompt logging was added)."
        )
    return PlainTextResponse(
        f"{'=' * 80}\nSYSTEM PROMPT\n{'=' * 80}\n\n{system_prompt or '(empty)'}\n\n"
        f"{'=' * 80}\nUSER PROMPT\n{'=' * 80}\n\n{user_prompt or '(empty)'}\n"
    )


@router.get("/{mapping_id}/response", response_class=PlainTextResponse)
def get_mapping_response(mapping_id: str):
    """The exact, unparsed text the LLM returned, before JSON extraction."""
    p = _find_path(mapping_id)
    if not p:
        raise HTTPException(404, "Mapping not found")
    d = json.loads(p.read_text())
    raw_response = d.get("raw_response")
    if not raw_response:
        return PlainTextResponse(
            "No raw response recorded for this mapping (not LLM-generated, "
            "or generated before response logging was added)."
        )
    return PlainTextResponse(raw_response)


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
