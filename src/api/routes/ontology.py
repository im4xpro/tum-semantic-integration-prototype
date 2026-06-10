from urllib.parse import unquote

from fastapi import APIRouter

from ..deps import get_ontology_manager

router = APIRouter()


@router.get("/classes")
def list_classes():
    manager = get_ontology_manager()
    return [c.model_dump() for c in manager.ontology.classes]


@router.get("/properties")
def list_properties():
    manager = get_ontology_manager()
    return [p.model_dump() for p in manager.ontology.properties]


@router.get("/classes/{class_uri:path}/properties")
def get_class_properties(class_uri: str):
    manager = get_ontology_manager()
    props = manager.get_properties_for_class(unquote(class_uri))
    return [p.model_dump() for p in props]
