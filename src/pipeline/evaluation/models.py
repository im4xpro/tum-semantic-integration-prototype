from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel

# Literal values are stored as their canonical Python type (Decimal, int, bool,
# date, datetime, or str) rather than re-stringified, so e.g. Decimal("9.0300")
# and Decimal("9.03") compare and hash equal — re-stringifying would lose that.
LiteralFact = tuple[str, Any]


@dataclass(frozen=True)
class SignatureEntity:
    """
    One real-world entity, normalized so gold and generated graphs can be
    compared regardless of which subject-URI scheme produced them.

    `key` is the entity's identity within its own graph (gold: temp_id,
    generated: subject URI) — only used to look up relations after matching,
    never compared across graphs. `class_uri`/`facts` (both fully-expanded
    URIs, literal values normalized) are what matching actually compares.
    """
    key: str
    class_uri: str
    facts: frozenset[LiteralFact]  # (predicate_uri, normalized_literal_value)

    @property
    def signature(self) -> tuple[str, frozenset[LiteralFact]]:
        return (self.class_uri, self.facts)


@dataclass(frozen=True)
class CanonicalRelation:
    """A relation triple expressed via matched-entity keys, not raw URIs."""
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
    accuracy: float
    entities_matched: int
    entities_unmatched_gold: int
    entities_unmatched_generated: int


class CQDefinition(BaseModel):
    id: str
    description: str = ""
    query_type: Literal["ask", "select"]
    query: str  # SPARQL with a {{graph}} placeholder
    expected: bool | list[dict[str, str]]


class CQResult(BaseModel):
    id: str
    passed: bool
    actual: bool | list[dict[str, Any]] | None = None
    error: str | None = None


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
    accuracy: float | None = None
    tp: int | None = None
    fp: int | None = None
    fn: int | None = None
    entities_matched: int | None = None
    entities_unmatched_gold: int | None = None
    entities_unmatched_generated: int | None = None
    cq_pass_rate: float | None = None
    n_cqs: int = 0
    n_cqs_passed: int = 0
    error: str | None = None
