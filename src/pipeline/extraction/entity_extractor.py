from datetime import datetime

from pipeline.mapping.models import MappingDocument
from pipeline.extraction.models import ExtractedEntity, ExtractedRelation, ExtractionResult


class EntityExtractor:

    def __init__(self, mapping: MappingDocument):
        self.mapping = mapping

    def extract(self, record: dict, source_name: str) -> ExtractionResult:
        source_record_id = self._get_record_id(record)

        entities: list[ExtractedEntity] = []
        entity_by_subject_col: dict[str, ExtractedEntity] = {}
        pending_relations: list[tuple[str, str, str]] = []  # (subject_temp_id, predicate_uri, object_col)

        # Pass 1: create all entities with their literal properties
        for sm in self.mapping.subject_mappings:
            subject_value = self._resolve(sm.subject.column_name, sm.subject.constant_value, record)
            if subject_value is None:
                continue

            class_uri = sm.type_mappings[0].class_uri if sm.type_mappings else "owl:Thing"
            properties = {}

            for pm in sm.property_mappings:
                for vd in pm.values:
                    value = self._resolve(vd.value_source.column_name, vd.value_source.constant_value, record)
                    if value is None:
                        continue
                    if vd.value_type.type == "literal":
                        properties[pm.property_uri] = value

            entity = ExtractedEntity(
                class_uri=class_uri,
                properties=properties,
                source_name=source_name,
                source_record_id=source_record_id,
            )
            entities.append(entity)

            if sm.subject.column_name:
                entity_by_subject_col[sm.subject.column_name] = entity

            for pm in sm.property_mappings:
                for vd in pm.values:
                    if vd.value_type.type == "iri" and vd.value_source.column_name:
                        pending_relations.append((entity.temp_id, pm.property_uri, vd.value_source.column_name))

        # Pass 2: resolve URI-type values as relations between entities
        relations: list[ExtractedRelation] = []
        for subject_id, predicate_uri, object_col in pending_relations:
            object_entity = entity_by_subject_col.get(object_col)
            if object_entity and object_entity.temp_id != subject_id:
                relations.append(ExtractedRelation(
                    subject_temp_id=subject_id,
                    predicate_uri=predicate_uri,
                    object_temp_id=object_entity.temp_id,
                ))

        return ExtractionResult(
            source_record=record,
            entities=entities,
            relations=relations,
            extraction_timestamp=datetime.now(),
            mapping_path=f"data/mappings/{self.mapping.source_name}_manual.json",
        )

    def _resolve(self, column_name: str | None, constant_value: str | None, record: dict) -> str | None:
        if column_name:
            value = record.get(column_name)
            return str(value) if value is not None and value != "" else None
        if constant_value is not None:
            return constant_value
        return None

    def _get_record_id(self, record: dict) -> str:
        for field in ["event_id_cnty", "id", "_id"]:
            if record.get(field):
                return str(record[field])
        return str(hash(str(record)))
