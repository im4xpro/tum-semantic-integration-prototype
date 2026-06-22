from collections import defaultdict
from typing import Any

from rdflib import RDF, Graph, Literal, Namespace, URIRef

from pipeline.extraction.models import ExtractionResult
from pipeline.graph.rdf_serializer import infer_literal, resolve_uri

from .models import CanonicalRelation, LiteralFact, MatchResult, SignatureEntity


def _canonicalize(value: Any) -> Any:
    """Strip plain strings; numeric/date/bool types are already canonical via infer_literal/toPython."""
    return value.strip() if isinstance(value, str) else value


def entities_from_extraction(
    results: list[ExtractionResult],
    namespaces: dict[str, Namespace],
    property_ranges: dict[str, URIRef],
) -> tuple[list[SignatureEntity], list[CanonicalRelation]]:
    """
    Build SignatureEntity/CanonicalRelation lists from gold ExtractionResults.
    Literal values go through the same infer_literal() typing RDFSerializer uses,
    so they normalize identically to what ends up in the generated graph.

    Entities are keyed and deduplicated by subject_uri (not by per-record
    temp_id): the same real-world entity (e.g. country="Spain") recurs across
    multiple sample records, and RDFSerializer.serialize_all() naturally
    merges those into one subject since a graph is a set of triples — the
    gold side must merge them the same way, or shared entities would wrongly
    show up as "missing" duplicates relative to the generated graph.
    """
    class_by_subject: dict[str, str] = {}
    facts_by_subject: dict[str, set[LiteralFact]] = defaultdict(set)
    relations: list[CanonicalRelation] = []

    for result in results:
        uri_by_temp_id = {entity.temp_id: entity.subject_uri for entity in result.entities}

        for entity in result.entities:
            class_by_subject[entity.subject_uri] = str(resolve_uri(entity.class_uri, namespaces))
            for pred_compact, values in entity.properties.items():
                pred = str(resolve_uri(pred_compact, namespaces))
                xsd_type = property_ranges.get(pred)
                for value in values:
                    typed = infer_literal(str(value), xsd_type).toPython()
                    facts_by_subject[entity.subject_uri].add((pred, _canonicalize(typed)))

        for relation in result.relations:
            subject_uri = uri_by_temp_id.get(relation.subject_temp_id, relation.subject_temp_id)
            object_uri = uri_by_temp_id.get(relation.object_temp_id, relation.object_temp_id)
            relations.append(CanonicalRelation(
                subject_key=subject_uri,
                predicate=str(resolve_uri(relation.predicate_uri, namespaces)),
                object_key=object_uri,
            ))

    entities = [
        SignatureEntity(key=subject_uri, class_uri=class_uri, facts=frozenset(facts_by_subject.get(subject_uri, set())))
        for subject_uri, class_uri in class_by_subject.items()
    ]
    return entities, relations


def entities_from_graph(g: Graph) -> tuple[list[SignatureEntity], list[CanonicalRelation]]:
    """
    Build SignatureEntity/CanonicalRelation lists from a generated rdflib Graph
    (fetched back from GraphDB). Subjects without an rdf:type triple are not
    entities under our model and are skipped.
    """
    types: dict[URIRef, set[URIRef]] = defaultdict(set)
    literal_facts: dict[URIRef, set[LiteralFact]] = defaultdict(set)
    relations: list[CanonicalRelation] = []

    for s, p, o in g:
        if p == RDF.type:
            types[s].add(o)
        elif isinstance(o, Literal):
            literal_facts[s].add((str(p), _canonicalize(o.toPython())))
        elif isinstance(o, URIRef):
            relations.append(CanonicalRelation(subject_key=str(s), predicate=str(p), object_key=str(o)))

    entities = [
        SignatureEntity(
            key=str(subject),
            class_uri=str(min(type_set, key=str)),  # deterministic if (unexpectedly) >1 type
            facts=frozenset(literal_facts.get(subject, set())),
        )
        for subject, type_set in types.items()
    ]
    return entities, relations


def _relation_context(
    entity_key: str,
    relations: list[CanonicalRelation],
    anchor_map: dict[str, str],
) -> frozenset[tuple[str, str, str]]:
    """
    A small "fingerprint" of an entity's relations to already-confidently-matched
    anchor entities: (direction, predicate, anchor's-partner-key). Used to break
    ties between otherwise-identical (same class + literal facts) entities.
    """
    context: set[tuple[str, str, str]] = set()
    for r in relations:
        if r.subject_key == entity_key and r.object_key in anchor_map:
            context.add(("out", r.predicate, anchor_map[r.object_key]))
        if r.object_key == entity_key and r.subject_key in anchor_map:
            context.add(("in", r.predicate, anchor_map[r.subject_key]))
    return frozenset(context)


def match_entities(
    gold: list[SignatureEntity],
    generated: list[SignatureEntity],
    gold_relations: list[CanonicalRelation] | None = None,
    generated_relations: list[CanonicalRelation] | None = None,
) -> MatchResult:
    """
    Match by signature (class_uri + literal facts) equality. Most signature
    buckets contain exactly one gold and one generated entity and match
    trivially (pass 1, "anchors"). When a bucket has duplicates on either side
    — multiple real-world entities that happen to share identical class +
    literal properties, e.g. several ActionEffect(fatalities=0) — pure content
    matching can't tell them apart; pass 2 breaks ties using one round of
    relation-based context against the pass-1 anchors (which entity does each
    ambiguous candidate relate to?). Residual ties (even relations don't
    distinguish them) fall back to arbitrary order — a documented limitation,
    not a bug: such entities are truly indistinguishable from the data alone.
    """
    gold_by_sig: dict[Any, list[SignatureEntity]] = defaultdict(list)
    for e in gold:
        gold_by_sig[e.signature].append(e)

    generated_by_sig: dict[Any, list[SignatureEntity]] = defaultdict(list)
    for e in generated:
        generated_by_sig[e.signature].append(e)

    matched_pairs: list[tuple[SignatureEntity, SignatureEntity]] = []
    ambiguous_sigs: list[Any] = []

    for sig in set(gold_by_sig) | set(generated_by_sig):
        gold_group = gold_by_sig.get(sig, [])
        generated_group = generated_by_sig.get(sig, [])
        if len(gold_group) == 1 and len(generated_group) == 1:
            matched_pairs.append((gold_group[0], generated_group[0]))
        else:
            ambiguous_sigs.append(sig)

    anchor_gold_to_generated = {g.key: n.key for g, n in matched_pairs}
    anchor_generated_to_gold = {n.key: g.key for g, n in matched_pairs}

    unmatched_gold: list[SignatureEntity] = []
    unmatched_generated: list[SignatureEntity] = []

    for sig in ambiguous_sigs:
        gold_group = list(gold_by_sig.get(sig, []))
        remaining_generated = list(generated_by_sig.get(sig, []))

        gold_contexts = {
            g.key: _relation_context(g.key, gold_relations or [], anchor_gold_to_generated) for g in gold_group
        }
        generated_contexts = {
            n.key: _relation_context(n.key, generated_relations or [], anchor_generated_to_gold)
            for n in remaining_generated
        }

        for g in gold_group:
            if not remaining_generated:
                unmatched_gold.append(g)
                continue
            best = max(
                remaining_generated,
                key=lambda n: len(gold_contexts[g.key] & generated_contexts[n.key]),  # noqa: B023
            )
            matched_pairs.append((g, best))
            remaining_generated.remove(best)
        unmatched_generated.extend(remaining_generated)

    return MatchResult(
        matched_pairs=matched_pairs,
        unmatched_gold=unmatched_gold,
        unmatched_generated=unmatched_generated,
    )
