import json
from pathlib import Path
from pipeline.mapping.models import MappingDocument
from pipeline.extraction.entity_extractor import EntityExtractor

BASE_DIR = Path(__file__).parent.parent

mapping = MappingDocument.model_validate(
    json.loads((BASE_DIR / "data/mappings/acled-manual.json").read_text())
)

record = {
    "event_id_cnty": "ESP105",
    "event_date": "2020-01-20",
    "event_type": "Protests",
    "sub_event_type": "Peaceful protest",
    "disorder_type": "Demonstrations",
    "actor1": "Protesters (Spain)",
    "assoc_actor_1": "Teachers (Spain)",
    "inter1": "Protesters",
    "actor2": None,
    "location": "Culleredo",
    "country": "Spain",
    "region": "Europe",
    "latitude": 43.2895,
    "longitude": -8.3894,
    "fatalities": 0,
    "notes": "On 20 January 2020, the educational community protested.",
    "source": "La Opinion A Coruna",
    "civilian_targeting": None,
}

extractor = EntityExtractor(mapping)
result = extractor.extract(record, "acled_data")

print(f"Entities: {len(result.entities)}")
for e in result.entities:
    print(f"  [{e.temp_id}] {e.class_uri}")
    for k, v in e.properties.items():
        print(f"    {k.split('#')[-1]}: {v}")

print(f"\nRelations: {len(result.relations)}")
for r in result.relations:
    print(f"  {r.subject_temp_id} --[{r.predicate_uri.split('#')[-1]}]--> {r.object_temp_id}")