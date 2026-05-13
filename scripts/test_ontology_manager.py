from pathlib import Path
from pipeline.ontology.manager import OntologyManager

BASE_DIR = Path(__file__).parent.parent
manager = OntologyManager(BASE_DIR / "data/ontology/thesis_ontology.ttl")

for fmt in ["compact", "class_list", "turtle"]:
    result = manager.get_formatted_ontology(fmt)
    print(f"\n=== {fmt} ({result.token_count} tokens) ===")
    print(result.content[:500])
    print("...")