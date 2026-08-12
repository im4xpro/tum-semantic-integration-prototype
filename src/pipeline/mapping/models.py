import enum
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from pipeline.mapping.llm_clients.factory import LLMProvider


class MappingBasis(enum.StrEnum):
    """The primary kind of evidence the model reports for a mapping decision."""

    # column / ontology-label name match
    NAME = "name"
    # matched the column description or the ontology term's rdfs:comment
    DESCRIPTION = "description"
    # sample values / datatype fit the range, or a discriminator value implies the class
    VALUE = "value"
    # inferred from the entity grouping / relationships rather than a single field
    STRUCTURAL = "structural"
    # no strong evidence; best guess
    WEAK = "weak"


def _coerce_basis(value: object) -> MappingBasis | None:
    # The LLM emits `basis` as free-form JSON text, so tolerate case/whitespace and
    # degrade any unrecognized value (e.g. "naming", "n/a", "") to None rather than
    # failing the whole document. A missing/unknown basis is simply "not reported".
    if isinstance(value, MappingBasis) or value is None:
        return value
    if not isinstance(value, str):
        return None
    try:
        return MappingBasis(value.strip().lower())
    except ValueError:
        return None


class PropertySource(BaseModel):
    source: Literal["column", "constant", "row_index"]
    column_name: str | None = None
    constant_value: str | None = None


class CodeTransformation(BaseModel):
    expression: str
    language: Literal["python"] = "python"


class TypeMapping(BaseModel):
    class_uri: str


class ValueType(BaseModel):
    type: Literal["literal", "iri"]
    type_mappings: list[TypeMapping] = []
    property_mappings: list["PropertyMapping"] = []


class ValueDefinition(BaseModel):
    value_source: PropertySource
    transformation: CodeTransformation | None = None
    value_type: ValueType = Field(default_factory=lambda: ValueType(type="literal"))


class PropertyMapping(BaseModel):
    property_uri: str
    values: list[ValueDefinition]
    # Confidence (0-1), evidence category, and justification for THIS column→property
    # choice specifically — a local decision, distinct from the subject-level
    # grouping/class decision below. None on manually-authored mappings and any
    # generated before these fields existed.
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    basis: MappingBasis | None = None
    reasoning: str | None = None

    _normalize_basis = field_validator("basis", mode="before")(_coerce_basis)


ValueType.model_rebuild()


class SubjectMapping(BaseModel):
    label: str | None = None
    subject: PropertySource
    subject_transformation: CodeTransformation | None = None
    type_mappings: list[TypeMapping] = []
    property_mappings: list[PropertyMapping] = []
    # Confidence (0-1), evidence category, and justification for THIS entity grouping
    # + class assignment — a structural decision, distinct from the per-property
    # confidence above. None on manually-authored mappings and any generated before
    # these fields existed.
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    basis: MappingBasis | None = None
    reasoning: str | None = None

    _normalize_basis = field_validator("basis", mode="before")(_coerce_basis)


class MappingStatus(enum.StrEnum):
    """Review state of a mapping document.

    Only APPROVED may be materialised into the knowledge graph. The default is DRAFT, so
    a document is never materialisable until a human has explicitly approved it — the
    guarantee is enforced server-side in POST /api/populate, not only in the editor.
    """

    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class MappingDocument(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_name: str
    status: MappingStatus = MappingStatus.DRAFT
    llm_model: str
    strategy: str
    ontology_format: str
    include_descriptions: bool
    base_uri: str = "https://thesis.tum.de/baltic-sea-monitoring/instances/"
    namespaces: dict[str, str] = {
        "bsm": "https://thesis.tum.de/baltic-sea-monitoring/ontology#"
    }
    subject_mappings: list[SubjectMapping]
    unmapped_fields: list[str] = []
    generation_timestamp: datetime
    prompt_tokens: int
    completion_tokens: int
    # only set for generated mappings
    system_prompt: str | None = None
    user_prompt: str | None = None
    raw_response: str | None = None


class MappingConfig(BaseModel):
    provider: LLMProvider
    llm_model: str
    strategy: Literal["zero_shot", "few_shot", "chain_of_thought"]
    ontology_format: Literal["turtle", "json_ld", "compact", "class_list"]
    include_descriptions: bool
    temperature: float = 0.0
