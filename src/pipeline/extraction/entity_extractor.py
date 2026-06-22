import re
from datetime import datetime
from urllib.parse import quote

from pipeline.extraction.models import (
    ExtractedEntity,
    ExtractedRelation,
    ExtractionResult,
)
from pipeline.mapping.models import CodeTransformation, MappingDocument, PropertySource


class EntityExtractor:

    def __init__(self, mapping: MappingDocument):
        self.mapping = mapping

    def extract(self, record: dict, source_name: str) -> ExtractionResult:
        source_record_id = self._get_record_id(record)

        entities: list[ExtractedEntity] = []
        # Keyed by local URI fragment (evaluated expression or raw column value),
        # so expression-only subjects like pt_{latitude}/{longitude} are reachable.
        entity_by_local_id: dict[str, ExtractedEntity] = {}
        pending_relations: list[tuple[str, str, str]] = []  # (temp_id, predicate_uri, object_local_id)

        # create all entities and collect pending IRI relations
        for sm in self.mapping.subject_mappings:
            local_id = self._local_id(sm.subject, sm.subject_transformation, record)
            if local_id is None:
                continue

            subject_uri = self.mapping.base_uri + local_id
            class_uri = sm.type_mappings[0].class_uri if sm.type_mappings else "owl:Thing"
            properties: dict[str, list] = {}

            for pm in sm.property_mappings:
                for vd in pm.values:
                    if vd.value_type.type != "literal":
                        continue
                    value = self._literal_value(vd.value_source, vd.transformation, record)
                    if value is None:
                        continue
                    properties.setdefault(pm.property_uri, []).append(value)

            entity = ExtractedEntity(
                subject_uri=subject_uri,
                class_uri=class_uri,
                properties=properties,
                source_name=source_name,
                source_record_id=source_record_id,
            )
            entities.append(entity)
            entity_by_local_id[local_id] = entity

            for pm in sm.property_mappings:
                for vd in pm.values:
                    if vd.value_type.type != "iri":
                        continue
                    ref_local_id = self._local_id(vd.value_source, vd.transformation, record)
                    if ref_local_id is None:
                        continue
                    pending_relations.append((entity.temp_id, pm.property_uri, ref_local_id))

        # resolve IRI references to relations between entities
        relations: list[ExtractedRelation] = []
        for subject_temp_id, predicate_uri, object_local_id in pending_relations:
            object_entity = entity_by_local_id.get(object_local_id)
            if object_entity and object_entity.temp_id != subject_temp_id:
                relations.append(ExtractedRelation(
                    subject_temp_id=subject_temp_id,
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

    # ── URI local-id computation ──────────────────────────────────────────────

    def _local_id(
        self,
        source: PropertySource,
        transformation: CodeTransformation | None,
        record: dict,
    ) -> str | None:
        """
        Returns the URI-safe local fragment for a subject or IRI value.
        Transformation expressions take precedence over the plain column value.
        Returns None if any referenced column is missing/empty so the entity
        or relation is silently skipped (e.g. optional assoc_actor_2).
        """
        if transformation is not None:
            result = self._eval_expr(transformation.expression, record)
            return _uri_safe(result) if result is not None else None
        if source.column_name:
            val = record.get(source.column_name)
            if val is None or str(val).strip() == "":
                return None
            return _uri_safe(str(val))
        if source.constant_value is not None:
            return _uri_safe(source.constant_value)
        return None

    # ── Literal value resolution (no URI encoding) ────────────────────────────

    def _literal_value(
        self,
        source: PropertySource,
        transformation: CodeTransformation | None,
        record: dict,
    ) -> str | None:
        if transformation is not None:
            return self._eval_expr(transformation.expression, record)
        if source.column_name:
            val = record.get(source.column_name)
            return str(val) if val is not None and str(val).strip() != "" else None
        if source.constant_value is not None:
            return source.constant_value
        return None

    # ── Expression evaluation ─────────────────────────────────────────────────

    @staticmethod
    def _eval_expr(expression: str, record: dict) -> str | None:
        """
        Evaluates a {column_name} template against a data record.
        Returns None if any referenced column is absent or empty so callers
        can skip the entity/value rather than producing a broken URI.
        """
        keys = re.findall(r'\{(\w+)\}', expression)
        for key in keys:
            val = record.get(key)
            if val is None or str(val).strip() == "":
                return None
        try:
            return expression.format_map({k: str(v) for k, v in record.items()})
        except Exception:
            return None

    # ── Record ID ─────────────────────────────────────────────────────────────

    @staticmethod
    def _get_record_id(record: dict) -> str:
        for field in ["event_id_cnty", "id", "_id"]:
            if record.get(field):
                return str(record[field])
        return str(hash(str(record)))


def _uri_safe(value: str) -> str:
    # Preserve slashes (compound keys like pt_52.5/13.4), underscores,
    # dots, and hyphens; percent-encode everything else including spaces.
    return quote(value, safe="_./-()")
