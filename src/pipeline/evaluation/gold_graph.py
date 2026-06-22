import json
from pathlib import Path

from rdflib import URIRef

from pipeline.connectors.sample_data import load_sample_records
from pipeline.extraction.entity_extractor import EntityExtractor
from pipeline.extraction.models import ExtractionResult
from pipeline.graph.rdf_serializer import build_property_ranges
from pipeline.mapping.models import MappingDocument
from pipeline.ontology.manager import OntologyManager


def build_gold_extraction_results(
    gold_mapping_path: Path,
    schemas_dir: Path,
    ontology_path: Path,
    data_limit: int | None = None,
) -> tuple[list[ExtractionResult], MappingDocument, dict[str, URIRef]]:
    """
    Load a hand-authored gold MappingDocument and run it through the same
    EntityExtractor every real run uses, against that source's real sample
    records — so the gold standard is derived the same way every
    LLM-generated mapping is, only the mapping itself differs.
    """
    mapping = MappingDocument.model_validate(json.loads(gold_mapping_path.read_text()))
    records = load_sample_records(mapping.source_name, schemas_dir)
    if data_limit:
        records = records[:data_limit]

    extractor = EntityExtractor(mapping)
    results = [extractor.extract(record, mapping.source_name) for record in records]

    ontology = OntologyManager(ontology_path).ontology
    property_ranges = build_property_ranges(ontology)

    return results, mapping, property_ranges
