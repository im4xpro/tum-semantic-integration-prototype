"""Tests for the confidence/reasoning fields on SubjectMapping/PropertyMapping.

Covers two guarantees the editor integration relies on:
- backward compatibility (existing corpus loads unchanged), and
- validation of the new confidence bounds at both mapping levels.
"""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from pipeline.mapping.models import MappingDocument, PropertyMapping, SubjectMapping

_REPO_ROOT = Path(__file__).parents[2]
_CORPUS_FILES = sorted((_REPO_ROOT / "data" / "mappings").glob("*.json")) + sorted(
    (_REPO_ROOT / "data" / "gold_standard").glob("*.gold.json")
)


def _subject_dict(**subject_extra) -> dict:
    # subject_extra applies only at the subject level, leaving the nested property
    # mapping clean so subject-level validation tests stay isolated from it.
    return {
        "subject": {"source": "column", "column_name": "order_id"},
        "type_mappings": [{"class_uri": "ex:Order"}],
        "property_mappings": [
            {
                "property_uri": "ex:total",
                "values": [
                    {"value_source": {"source": "column", "column_name": "total"}}
                ],
            }
        ],
        **subject_extra,
    }


def test_corpus_present():
    # Guards against the parametrized backward-compat test silently collecting nothing.
    assert _CORPUS_FILES, "no mapping/gold files found under data/ to test against"


@pytest.mark.parametrize("path", _CORPUS_FILES, ids=lambda p: p.name)
def test_existing_corpus_still_loads(path: Path):
    # Every pre-existing mapping/gold document (written before confidence/reasoning
    # existed, including hand-authored ones) must still validate.
    MappingDocument.model_validate(json.loads(path.read_text()))


def test_missing_confidence_reasoning_defaults_to_none():
    # A mapping with neither key present parses, defaulting both fields to None
    # at the subject and the property level.
    sm = SubjectMapping.model_validate(_subject_dict())
    assert sm.confidence is None and sm.reasoning is None
    assert sm.property_mappings[0].confidence is None
    assert sm.property_mappings[0].reasoning is None


@pytest.mark.parametrize("bad_value", [1.5, -0.1])
def test_subject_confidence_out_of_range_rejected(bad_value: float):
    with pytest.raises(ValidationError):
        SubjectMapping.model_validate(_subject_dict(confidence=bad_value))


@pytest.mark.parametrize("bad_value", [1.5, -0.1])
def test_property_confidence_out_of_range_rejected(bad_value: float):
    with pytest.raises(ValidationError):
        PropertyMapping.model_validate(
            {
                "property_uri": "ex:total",
                "confidence": bad_value,
                "values": [
                    {"value_source": {"source": "column", "column_name": "total"}}
                ],
            }
        )


@pytest.mark.parametrize("good_value", [0.0, 0.5, 1.0])
def test_confidence_bounds_inclusive(good_value: float):
    # The [0, 1] bounds are inclusive on both models.
    assert SubjectMapping.model_validate(_subject_dict(confidence=good_value))
    assert PropertyMapping.model_validate(
        {
            "property_uri": "ex:total",
            "confidence": good_value,
            "values": [{"value_source": {"source": "column", "column_name": "total"}}],
        }
    )
