"""Tests for the confidence/basis/reasoning fields on SubjectMapping/PropertyMapping.

Covers the guarantees the editor integration relies on:
- backward compatibility (existing corpus loads unchanged),
- validation of the confidence bounds at both mapping levels, and
- robust coercion of the free-text `basis` tag (valid -> enum, unknown -> None).
"""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from pipeline.mapping.models import (
    MappingBasis,
    MappingDocument,
    PropertyMapping,
    SubjectMapping,
)

_REPO_ROOT = Path(__file__).parents[2]
_CORPUS_FILES = sorted((_REPO_ROOT / "data" / "mappings").glob("*.json")) + sorted(
    (_REPO_ROOT / "data" / "gold_standard").glob("*.gold.json")
)


def _property_dict(**extra) -> dict:
    return {
        "property_uri": "ex:total",
        "values": [{"value_source": {"source": "column", "column_name": "total"}}],
        **extra,
    }


def _subject_dict(**subject_extra) -> dict:
    # subject_extra applies only at the subject level, leaving the nested property
    # mapping clean so subject-level validation tests stay isolated from it.
    return {
        "subject": {"source": "column", "column_name": "order_id"},
        "type_mappings": [{"class_uri": "ex:Order"}],
        "property_mappings": [_property_dict()],
        **subject_extra,
    }


def _subject_with(**extra) -> SubjectMapping:
    return SubjectMapping.model_validate(_subject_dict(**extra))


def _property_with(**extra) -> PropertyMapping:
    return PropertyMapping.model_validate(_property_dict(**extra))


# Exercises the shared `basis` coercion on both models that carry it.
_BUILDERS = [
    pytest.param(_subject_with, id="subject"),
    pytest.param(_property_with, id="property"),
]


def test_corpus_present():
    # Guards against the parametrized backward-compat test silently collecting nothing.
    assert _CORPUS_FILES, "no mapping/gold files found under data/ to test against"


@pytest.mark.parametrize("path", _CORPUS_FILES, ids=lambda p: p.name)
def test_existing_corpus_still_loads(path: Path):
    # Every pre-existing mapping/gold document (written before confidence/reasoning
    # existed, including hand-authored ones) must still validate.
    MappingDocument.model_validate(json.loads(path.read_text()))


def test_missing_optional_fields_default_to_none():
    # A mapping with none of confidence/basis/reasoning present parses, defaulting
    # all three to None at the subject and the property level.
    sm = SubjectMapping.model_validate(_subject_dict())
    assert (sm.confidence, sm.basis, sm.reasoning) == (None, None, None)
    pm = sm.property_mappings[0]
    assert (pm.confidence, pm.basis, pm.reasoning) == (None, None, None)


@pytest.mark.parametrize("bad_value", [1.5, -0.1])
def test_subject_confidence_out_of_range_rejected(bad_value: float):
    with pytest.raises(ValidationError):
        SubjectMapping.model_validate(_subject_dict(confidence=bad_value))


@pytest.mark.parametrize("bad_value", [1.5, -0.1])
def test_property_confidence_out_of_range_rejected(bad_value: float):
    with pytest.raises(ValidationError):
        PropertyMapping.model_validate(_property_dict(confidence=bad_value))


@pytest.mark.parametrize("good_value", [0.0, 0.5, 1.0])
def test_confidence_bounds_inclusive(good_value: float):
    # The [0, 1] bounds are inclusive on both models.
    assert _subject_with(confidence=good_value)
    assert _property_with(confidence=good_value)


@pytest.mark.parametrize("build", _BUILDERS)
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("name", MappingBasis.NAME),
        ("description", MappingBasis.DESCRIPTION),
        ("value", MappingBasis.VALUE),
        ("structural", MappingBasis.STRUCTURAL),
        ("weak", MappingBasis.WEAK),
        ("STRUCTURAL", MappingBasis.STRUCTURAL),  # case-insensitive
        ("  Value  ", MappingBasis.VALUE),  # whitespace-tolerant
    ],
)
def test_basis_accepts_valid_values(build, raw, expected):
    assert build(basis=raw).basis is expected


@pytest.mark.parametrize("build", _BUILDERS)
@pytest.mark.parametrize("bad", ["naming", "n/a", "", "xyz", 7, None])
def test_unrecognized_or_missing_basis_coerces_to_none(build, bad):
    # An unknown or non-string basis degrades to None instead of raising, so a
    # stray LLM value never fails the whole document.
    assert build(basis=bad).basis is None
