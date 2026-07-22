#!/usr/bin/env python3
"""
Demo: Extraction + RDF Serialization pipeline
----------------------------------------------
Loads the manual ACLED mapping and the 5 sample records embedded in the
postgres schema file, runs extraction + serialization on each record, and
writes the combined graph to data/output/demo.ttl.

Shows per-record stats, cross-record subject deduplication, and a breakdown
of triple types in the final graph.
"""

import sys
import json
import logging
from pathlib import Path
from collections import defaultdict

# rdflib logs a warning when it can't coerce a lexical form to a Python value
# (e.g. a Unix timestamp integer stored with xsd:dateTime datatype). The triple
# is still written correctly — suppress the noise so the demo output is readable.
logging.getLogger("rdflib").setLevel(logging.ERROR)

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rdflib import RDF  # noqa: E402
from pipeline.mapping.models import MappingDocument  # noqa: E402
from pipeline.ontology.manager import OntologyManager  # noqa: E402
from pipeline.extraction.entity_extractor import EntityExtractor  # noqa: E402
from pipeline.extraction.models import ExtractionResult  # noqa: E402
from pipeline.graph.rdf_serializer import RDFSerializer, build_property_ranges  # noqa: E402

# ── Paths ─────────────────────────────────────────────────────────────────────

BASE = Path(__file__).parent.parent
MAPPING = BASE / "data/mappings/acled-manual.json"
SCHEMA = BASE / "data/schemas/postgres_schema.json"
ONTOLOGY = BASE / "data/ontology/thesis_ontology.ttl"
OUT_DIR = BASE / "data/output"
OUT_TTL = OUT_DIR / "demo.ttl"

# ── Load ──────────────────────────────────────────────────────────────────────

mapping = MappingDocument.model_validate(json.loads(MAPPING.read_text()))
ontology = OntologyManager(ONTOLOGY).ontology
records = json.loads(SCHEMA.read_text()).get("sample_records", [])

prop_ranges = build_property_ranges(ontology)
extractor = EntityExtractor(mapping)
serializer = RDFSerializer(mapping, property_ranges=prop_ranges)

print(f"\n{'─' * 64}")
print(f"  Mapping : {MAPPING.name}")
print(f"  Records : {len(records)} sample records from {SCHEMA.name}")
print(f"  Prop. ranges resolved from ontology: {len(prop_ranges)}")
print(f"{'─' * 64}\n")

# ── Per-record extraction ─────────────────────────────────────────────────────

results: list[ExtractionResult] = []

for i, record in enumerate(records, 1):
    result = extractor.extract(record, mapping.source_name)
    results.append(result)

    entity_labels = []
    for e in result.entities:
        cls = e.class_uri.split(":")[-1].split("#")[-1]
        local = e.subject_uri.split("/")[-1]
        entity_labels.append(f"{cls}({local[:30]})")

    skipped_cols = [
        col
        for col in ["actor2", "assoc_actor_1", "assoc_actor_2"]
        if not record.get(col)
    ]

    print(f"  Record {i}  [{record['event_id_cnty']}]  {record.get('country', '')}")
    print(f"    entities  : {len(result.entities)}")
    print(f"    relations : {len(result.relations)}")
    if skipped_cols:
        print(f"    skipped   : {', '.join(skipped_cols)} (null/empty)")
    for label in entity_labels:
        print(f"      · {label}")
    print()

# ── Serialize all records into one graph ─────────────────────────────────────

graph = serializer.serialize_all(results)

# ── Stats ─────────────────────────────────────────────────────────────────────

subjects = set(s for s, p, o in graph)
types_map = defaultdict(set)  # class_uri → set of subject URIs
preds_map = defaultdict(int)  # predicate → count

for s, p, o in graph:
    preds_map[str(p)] += 1
    if p == RDF.type:
        types_map[str(o)].add(str(s))

print(f"{'─' * 64}")
print("  Combined graph")
print(f"{'─' * 64}")
print(f"  Total triples   : {len(graph)}")
print(f"  Unique subjects : {len(subjects)}")
print()

print("  Instances by type:")
for class_uri, instances in sorted(types_map.items(), key=lambda x: -len(x[1])):
    label = class_uri.split("#")[-1].split(":")[-1]
    print(f"    {label:<24} {len(instances):>3} instance(s)")
print()

print("  Triples by predicate:")
for pred, count in sorted(preds_map.items(), key=lambda x: -x[1]):
    label = pred.split("#")[-1].split(":")[-1]
    print(f"    {label:<36} {count:>3}")
print()

# Note on Unix timestamps
ts_vals = [str(r.get("timestamp", "")) for r in records]
if any(v.isdigit() for v in ts_vals):
    print("  NOTE: 'timestamp' column contains Unix epoch integers.")
    print("        eventEndDateTime triples use xsd:dateTime datatype but the")
    print("        value '1729023384' is not ISO 8601 — a mapping-level")
    print("        transformation (e.g. expr mode) should convert it before")
    print("        the data reaches GraphDB.\n")

# ── Write Turtle ──────────────────────────────────────────────────────────────

OUT_DIR.mkdir(parents=True, exist_ok=True)
turtle = graph.serialize(format="turtle")
OUT_TTL.write_text(turtle)
print(f"  Turtle written → {OUT_TTL.relative_to(BASE)}")
print(f"{'─' * 64}\n")
print(turtle)
