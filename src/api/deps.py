from pathlib import Path

from pipeline.ontology.manager import OntologyManager

DATA_DIR = Path(__file__).parent.parent.parent / "data"
ONTOLOGY_PATH = DATA_DIR / "ontology" / "thesis_ontology.ttl"
SCHEMAS_DIR = DATA_DIR / "schemas"
MAPPINGS_DIR = DATA_DIR / "mappings"

_ontology_manager: OntologyManager | None = None


def get_ontology_manager() -> OntologyManager:
    global _ontology_manager
    if _ontology_manager is None:
        _ontology_manager = OntologyManager(ONTOLOGY_PATH)
    return _ontology_manager
