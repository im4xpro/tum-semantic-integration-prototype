#!/usr/bin/env python3
"""
Smoke-test for the updated EntityExtractor.

Exercises:
  - expression-based subject URIs (action_, org_, loc_, pt_)
  - expression-only subject (Point has no column_name, identity is pt_{lat}/{lon})
  - multi-value IRI relations (4 x involvedActor, but assoc_actor_2 is empty → skipped)
  - null optional column skipped cleanly
  - multi-value literal storage (list per predicate)
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pipeline.mapping.models import MappingDocument
from pipeline.extraction.entity_extractor import EntityExtractor

MAPPING_PATH = Path(__file__).parent.parent / "data/mappings/acled-manual.json"

SAMPLE_RECORD = {
    "event_id_cnty": "ETH1234",
    "timestamp": "2024-01-15T12:00:00",
    "notes": "Clashes reported near Addis Ababa.",
    "location": "Addis Ababa",
    "latitude": "9.0300",
    "longitude": "38.7400",
    "actor1": "Ethiopian National Defence Force",
    "assoc_actor_1": "Federal Police",
    "actor2": "Tigray People Liberation Front",
    "assoc_actor_2": "",   # intentionally empty → entity + relation must be skipped
}


def main():
    mapping = MappingDocument.model_validate(json.loads(MAPPING_PATH.read_text()))
    extractor = EntityExtractor(mapping)
    result = extractor.extract(SAMPLE_RECORD, mapping.source_name)

    print(f"\n{'='*60}")
    print(f"  Entities:  {len(result.entities)}")
    print(f"  Relations: {len(result.relations)}")
    print(f"{'='*60}\n")

    entity_by_temp = {e.temp_id: e for e in result.entities}

    for e in result.entities:
        print(f"  [{e.temp_id}]  <{e.subject_uri}>")
        print(f"              rdf:type  {e.class_uri}")
        for pred, vals in e.properties.items():
            label = pred.split("#")[-1].split(":")[-1]
            print(f"              {label}: {vals}")
        print()

    print("  Relations:")
    for r in result.relations:
        subj = entity_by_temp[r.subject_temp_id].subject_uri
        obj  = entity_by_temp[r.object_temp_id].subject_uri
        pred = r.predicate_uri.split("#")[-1].split(":")[-1]
        print(f"    <.../{subj.split('/')[-1]}> --[{pred}]--> <.../{obj.split('/')[-1]}>")
    print()

    # ── Assertions ────────────────────────────────────────────────────────────
    uris = {e.subject_uri for e in result.entities}

    assert any("action_ETH1234" in u for u in uris), \
        f"Action URI missing. URIs: {uris}"

    assert any("loc_" in u for u in uris), \
        f"Location URI missing. URIs: {uris}"

    assert any("pt_9.0300" in u for u in uris), \
        "Point URI missing — expression-only subject (pt_{{lat}}/{{lon}}) not evaluated"

    org_entities = [e for e in result.entities if "Organisation" in e.class_uri]
    assert len(org_entities) == 3, (
        f"Expected 3 org entities (assoc_actor_2 empty → skip), got {len(org_entities)}"
    )

    actor_rels = [r for r in result.relations if "involvedActor" in r.predicate_uri]
    assert len(actor_rels) == 3, (
        f"Expected 3 involvedActor relations, got {len(actor_rels)}"
    )

    geo_rels = [r for r in result.relations if "hasGeometry" in r.predicate_uri]
    assert len(geo_rels) == 1, (
        f"Expected 1 hasGeometry (Location→Point), got {len(geo_rels)}"
    )

    loc_rels = [r for r in result.relations if "hasGeographicLocation" in r.predicate_uri]
    assert len(loc_rels) == 1, \
        f"Expected 1 hasGeographicLocation (Action→Location), got {len(loc_rels)}"

    print("  All assertions passed.")


if __name__ == "__main__":
    main()
