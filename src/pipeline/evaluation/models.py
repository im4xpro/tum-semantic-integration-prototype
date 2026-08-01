from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel

# Literal values are stored as their canonical Python type (Decimal, int, bool,
# date, datetime, or str) rather than re-stringified, so e.g. Decimal("9.0300")
# and Decimal("9.03") compare and hash equal — re-stringifying would lose that.
LiteralFact = tuple[str, Any]


@dataclass(frozen=True)
class SignatureEntity:
    # `key` is only used to look up relations after matching, never compared
    # across graphs — gold uses temp_id, generated uses subject URI.
    key: str
    class_uri: str
    facts: frozenset[LiteralFact]  # (predicate_uri, normalized_literal_value)


@dataclass(frozen=True)
class CanonicalRelation:
    subject_key: str
    predicate: str
    object_key: str


@dataclass
class MatchResult:
    matched_pairs: list[tuple[SignatureEntity, SignatureEntity]]  # (gold, generated)
    unmatched_gold: list[SignatureEntity]
    unmatched_generated: list[SignatureEntity]


class EvaluationMetrics(BaseModel):
    tp: int
    fp: int
    fn: int
    precision: float
    recall: float
    f1: float
    entities_matched: int
    entities_unmatched_gold: int
    entities_unmatched_generated: int


class FieldDiff(BaseModel):
    source_fields: list[str]
    gold_predicate: str | None
    generated_predicate: str | None
    status: Literal["match", "mismatch", "fn", "fp"]


class SubjectDiff(BaseModel):
    class_uri: str
    subject_column: str
    field_diffs: list[FieldDiff]


class MappingDiff(BaseModel):
    run_id: str
    llm_model: str
    strategy: str
    ontology_format: str
    include_descriptions: bool
    error: str | None = None
    tp: int = 0
    fp: int = 0
    fn: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    subject_diffs: list[SubjectDiff] = []


class FactDiff(BaseModel):
    predicate: str
    value: str
    status: Literal["tp", "fn", "fp"]


class EntityPairDiff(BaseModel):
    gold_facts: list[FactDiff]
    generated_facts: list[FactDiff]


class ClassDiff(BaseModel):
    class_uri: str
    matched: list[EntityPairDiff]
    unmatched_gold: list[list[FactDiff]]
    unmatched_generated: list[list[FactDiff]]


class RelationDiff(BaseModel):
    """One object-property statement, scored exactly as compute_metrics scores it."""

    subject: str
    predicate: str
    object: str
    status: Literal["tp", "fn", "fp"]


class RunDiff(BaseModel):
    run_id: str
    llm_model: str
    strategy: str
    ontology_format: str
    include_descriptions: bool
    error: str | None = None
    class_diffs: list[ClassDiff] = []
    relation_diffs: list[RelationDiff] = []


class EvaluationResult(BaseModel):
    run_id: str
    experiment_name: str
    provider: str
    llm_model: str
    strategy: str
    ontology_format: str
    include_descriptions: bool
    precision: float | None = None
    recall: float | None = None
    f1: float | None = None
    tp: int | None = None
    fp: int | None = None
    fn: int | None = None
    entities_matched: int | None = None
    entities_unmatched_gold: int | None = None
    entities_unmatched_generated: int | None = None
    error: str | None = None
