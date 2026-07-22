from collections import defaultdict
from typing import Any

from rdflib import RDF, Graph, Literal, Namespace, URIRef

from pipeline.extraction.models import ExtractionResult
from pipeline.graph.rdf_serializer import infer_literal, resolve_uri

from .models import CanonicalRelation, LiteralFact, MatchResult, SignatureEntity


def _canonicalize(value: Any) -> Any:
    # Numeric/date/bool types coming from toPython() are already canonical; only strings need stripping.
    return value.strip() if isinstance(value, str) else value


def entities_from_extraction(
    results: list[ExtractionResult],
    namespaces: dict[str, Namespace],
    property_ranges: dict[str, URIRef],
) -> tuple[list[SignatureEntity], list[CanonicalRelation]]:
    # Literal values go through the same infer_literal() typing RDFSerializer uses,
    # so they normalize identically to what ends up in the generated graph.
    #
    # Entities are keyed and deduplicated by subject_uri (not by per-record temp_id):
    # the same real-world entity (e.g. country="Spain") recurs across multiple sample
    # records, and RDFSerializer.serialize_all() naturally merges those into one subject
    # since a graph is a set of triples — the gold side must merge them the same way,
    # or shared entities would wrongly show up as "missing" duplicates.
    class_by_subject: dict[str, str] = {}
    facts_by_subject: dict[str, set[LiteralFact]] = defaultdict(set)
    relations: list[CanonicalRelation] = []

    for result in results:
        uri_by_temp_id = {
            entity.temp_id: entity.subject_uri for entity in result.entities
        }

        for entity in result.entities:
            class_by_subject[entity.subject_uri] = str(
                resolve_uri(entity.class_uri, namespaces)
            )
            for pred_compact, values in entity.properties.items():
                pred = str(resolve_uri(pred_compact, namespaces))
                xsd_type = property_ranges.get(pred)
                for value in values:
                    typed = infer_literal(str(value), xsd_type).toPython()
                    facts_by_subject[entity.subject_uri].add(
                        (pred, _canonicalize(typed))
                    )

        for relation in result.relations:
            subject_uri = uri_by_temp_id.get(
                relation.subject_temp_id, relation.subject_temp_id
            )
            object_uri = uri_by_temp_id.get(
                relation.object_temp_id, relation.object_temp_id
            )
            relations.append(
                CanonicalRelation(
                    subject_key=subject_uri,
                    predicate=str(resolve_uri(relation.predicate_uri, namespaces)),
                    object_key=object_uri,
                )
            )

    entities = [
        SignatureEntity(
            key=subject_uri,
            class_uri=class_uri,
            facts=frozenset(facts_by_subject.get(subject_uri, set())),
        )
        for subject_uri, class_uri in class_by_subject.items()
    ]
    return entities, relations


def entities_from_graph(
    g: Graph,
) -> tuple[list[SignatureEntity], list[CanonicalRelation]]:
    # Subjects without an rdf:type triple are not entities under our model and are skipped.
    types: dict[URIRef, set[URIRef]] = defaultdict(set)
    literal_facts: dict[URIRef, set[LiteralFact]] = defaultdict(set)
    relations: list[CanonicalRelation] = []

    for s, p, o in g:
        if p == RDF.type:
            types[s].add(o)
        elif isinstance(o, Literal):
            literal_facts[s].add((str(p), _canonicalize(o.toPython())))
        elif isinstance(o, URIRef):
            relations.append(
                CanonicalRelation(
                    subject_key=str(s), predicate=str(p), object_key=str(o)
                )
            )

    entities = [
        SignatureEntity(
            key=str(subject),
            class_uri=str(
                min(type_set, key=str)
            ),  # deterministic if (unexpectedly) >1 type
            facts=frozenset(literal_facts.get(subject, set())),
        )
        for subject, type_set in types.items()
    ]
    return entities, relations


def _group_by_class(
    entities: list[SignatureEntity],
) -> dict[str, list[SignatureEntity]]:
    groups: dict[str, list[SignatureEntity]] = defaultdict(list)
    for e in entities:
        groups[e.class_uri].append(e)
    return groups


def match_entities(
    gold: list[SignatureEntity],
    generated: list[SignatureEntity],
) -> MatchResult:
    # Two entities can only match if they share the same class_uri and at least one
    # (predicate, value) pair. Pairs are ranked by overlap size and assigned greedily
    # (highest overlap first, no entity used twice). This tolerates LLM-generated
    # mappings that use different — but partially overlapping — predicates than the
    # gold standard, while still requiring agreement on both predicate and value to
    # score a TP. Entities with no overlap are left unmatched: FN (gold) / FP (generated).
    gold_by_class = _group_by_class(gold)
    gen_by_class = _group_by_class(generated)

    matched_pairs: list[tuple[SignatureEntity, SignatureEntity]] = []
    unmatched_gold: list[SignatureEntity] = []
    unmatched_generated: list[SignatureEntity] = []

    for class_uri in set(gold_by_class) | set(gen_by_class):
        g_group = gold_by_class.get(class_uri, [])
        n_group = gen_by_class.get(class_uri, [])

        if not g_group:
            unmatched_generated.extend(n_group)
            continue
        if not n_group:
            unmatched_gold.extend(g_group)
            continue

        scored = sorted(
            [(len(g.facts & n.facts), g, n) for g in g_group for n in n_group],
            key=lambda t: -t[0],
        )

        used_gold: set[str] = set()
        used_gen: set[str] = set()

        for overlap, g, n in scored:
            if overlap == 0:
                break
            if g.key in used_gold or n.key in used_gen:
                continue
            matched_pairs.append((g, n))
            used_gold.add(g.key)
            used_gen.add(n.key)

        unmatched_gold.extend(g for g in g_group if g.key not in used_gold)
        unmatched_generated.extend(n for n in n_group if n.key not in used_gen)

    return MatchResult(matched_pairs, unmatched_gold, unmatched_generated)
