#!/usr/bin/env python3
"""Manual check: parse the ontology TTL and print class/property counts."""

from pathlib import Path

from pipeline.ontology.ontology_loader import OntologyLoader

BASE_DIR = Path(__file__).parent.parent

loader = OntologyLoader()
ontology = loader.load(BASE_DIR / "data/ontology/thesis_ontology.ttl")

print(f"Classes:    {len(ontology.classes)}")
print(f"Properties: {len(ontology.properties)}")
print(f"Prefix:     {ontology.prefix}")
print(f"Namespace:  {ontology.namespace}")

print("\n--- Sample Classes ---")
for cls in ontology.classes[:5]:
    print(f"  {cls.label} (extension: {cls.is_extension})")
    if cls.subclass_of:
        print(f"    subClassOf: {cls.subclass_of[0].split('#')[-1]}")

print("\n--- Sample Properties ---")
for prop in ontology.properties[:5]:
    print(f"  {prop.label} ({'obj' if prop.is_object_property else 'data'})")
    if prop.domain:
        print(f"    domain: {prop.domain[0].split('#')[-1]}")
