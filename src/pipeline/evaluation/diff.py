import json
from pathlib import Path

from rdflib import URIRef

from pipeline.extraction.models import ExtractionResult
from pipeline.graph.graphdb_client import GraphDBClient
from pipeline.graph.rdf_serializer import build_namespaces
from pipeline.mapping.models import MappingDocument, SubjectMapping
from pipeline.runner.models import Run, RunStatus
from pipeline.runner.pipeline_runner import build_graphdb_config

from .models import (
    CanonicalRelation,
    ClassDiff,
    EntityPairDiff,
    FactDiff,
    FieldDiff,
    MappingDiff,
    MatchResult,
    RelationDiff,
    RunDiff,
    SubjectDiff,
)
from .signatures import entities_from_extraction, entities_from_graph, match_entities
from .triple_metrics import _prf

_MAPPINGS_DIR = Path(__file__).parent.parent.parent.parent / "data" / "mappings"


def _load_generated_mapping(run: Run) -> MappingDocument | None:
    if not run.mapping_id:
        return None
    for p in _MAPPINGS_DIR.glob("*.json"):
        try:
            d = json.loads(p.read_text())
            if d.get("id") == run.mapping_id or p.stem == run.mapping_id:
                return MappingDocument.model_validate(d)
        except Exception:
            pass
    return None


def _index_subject(sm: SubjectMapping) -> tuple[str, str]:
    class_uri = sm.type_mappings[0].class_uri if sm.type_mappings else "?"
    subj_col = sm.subject.column_name or sm.subject.constant_value or "?"
    return (class_uri, subj_col)


def _field_pairs(sm: SubjectMapping) -> dict[frozenset[str], str]:
    pairs: dict[frozenset[str], str] = {}
    for pm in sm.property_mappings:
        cols = frozenset(
            v.value_source.column_name
            for v in pm.values
            if v.value_source and v.value_source.column_name
        )
        if cols:
            pairs[cols] = pm.property_uri
    return pairs


def _run_base(run: Run) -> dict:
    return dict(
        run_id=run.id,
        llm_model=run.config.llm_model,
        strategy=run.config.strategy,
        ontology_format=run.config.ontology_format,
        include_descriptions=run.config.include_descriptions,
    )


def diff_mappings(run: Run, gold_mapping: MappingDocument) -> MappingDiff:
    base = _run_base(run)

    gen_mapping = _load_generated_mapping(run)
    if gen_mapping is None:
        return MappingDiff(**base, error="Generated mapping not found")

    gold_by_key: dict[tuple[str, str], dict[frozenset[str], str]] = {}
    for sm in gold_mapping.subject_mappings:
        gold_by_key[_index_subject(sm)] = _field_pairs(sm)

    gen_by_key: dict[tuple[str, str], dict[frozenset[str], str]] = {}
    for sm in gen_mapping.subject_mappings:
        gen_by_key[_index_subject(sm)] = _field_pairs(sm)

    all_keys = sorted(set(gold_by_key) | set(gen_by_key))
    subject_diffs: list[SubjectDiff] = []
    tp = fp = fn = 0

    for class_uri, subj_col in all_keys:
        gold_pairs = gold_by_key.get((class_uri, subj_col), {})
        gen_pairs = gen_by_key.get((class_uri, subj_col), {})
        all_col_sets = sorted(set(gold_pairs) | set(gen_pairs), key=lambda s: sorted(s))

        field_diffs: list[FieldDiff] = []
        for col_set in all_col_sets:
            gp = gold_pairs.get(col_set)
            np_ = gen_pairs.get(col_set)
            if gp and np_:
                if gp == np_:
                    status = "match"
                    tp += 1
                else:
                    status = "mismatch"
                    fp += 1
                    fn += 1
            elif gp:
                status = "fn"
                fn += 1
            else:
                status = "fp"
                fp += 1
            field_diffs.append(
                FieldDiff(
                    source_fields=sorted(col_set),
                    gold_predicate=gp,
                    generated_predicate=np_,
                    status=status,
                )
            )

        subject_diffs.append(
            SubjectDiff(
                class_uri=class_uri, subject_column=subj_col, field_diffs=field_diffs
            )
        )

    precision, recall, f1 = _prf(tp, fp, fn)

    return MappingDiff(
        **base,
        tp=tp,
        fp=fp,
        fn=fn,
        precision=precision,
        recall=recall,
        f1=f1,
        subject_diffs=subject_diffs,
    )


def _compact(uri: str, ns_map: dict[str, str]) -> str:
    for prefix, ns in ns_map.items():
        if uri.startswith(ns):
            return f"{prefix}:{uri[len(ns) :]}"
    return uri.rsplit("#", 1)[-1] if "#" in uri else uri.rsplit("/", 1)[-1]


def diff_run(
    run: Run,
    gold_results: list[ExtractionResult],
    gold_mapping: MappingDocument,
    gold_property_ranges: dict[str, URIRef],
) -> RunDiff:
    base = _run_base(run)

    if run.status != RunStatus.completed or not run.named_graph:
        return RunDiff(**base, error="run not completed or has no named graph")

    try:
        client = GraphDBClient(build_graphdb_config(run.config))
        generated_graph = client.construct_named_graph(run.named_graph)
    except Exception as e:
        return RunDiff(**base, error=str(e))

    gold_namespaces = build_namespaces(gold_mapping)
    gold_entities, gold_relations = entities_from_extraction(
        gold_results, gold_namespaces, gold_property_ranges
    )
    generated_entities, generated_relations = entities_from_graph(generated_graph)

    match = match_entities(gold_entities, generated_entities)

    ns_map = {px: str(ns) for px, ns in gold_namespaces.items()}

    def compact(uri: str) -> str:
        return _compact(uri, ns_map)

    # Facts hold heterogeneous value types (Decimal, int, str, date), so sorting the
    # raw tuples raises TypeError whenever one predicate carries two different types.
    def by_predicate(facts) -> list:
        return sorted(facts, key=lambda f: (f[0], str(f[1])))

    def type_row(class_uri: str, status: str) -> FactDiff:
        # rdf:type is a scored statement, so it belongs in the breakdown; without it
        # the displayed facts do not account for everything the metric counts.
        return FactDiff(predicate="rdf:type", value=compact(class_uri), status=status)  # pyright: ignore[reportArgumentType]

    by_class: dict[str, ClassDiff] = {}

    def get_cd(cls_uri: str) -> ClassDiff:
        if cls_uri not in by_class:
            by_class[cls_uri] = ClassDiff(
                class_uri=cls_uri, matched=[], unmatched_gold=[], unmatched_generated=[]
            )
        return by_class[cls_uri]

    for gold_e, gen_e in match.matched_pairs:
        tp = gold_e.facts & gen_e.facts
        # The class always agrees inside a matched pair — it is a precondition of matching.
        gold_side = [type_row(gold_e.class_uri, "tp")] + [
            FactDiff(
                predicate=compact(p),
                value=str(v)[:200],
                status="tp" if (p, v) in tp else "fn",
            )
            for p, v in by_predicate(gold_e.facts)
        ]
        gen_side = [type_row(gen_e.class_uri, "tp")] + [
            FactDiff(
                predicate=compact(p),
                value=str(v)[:200],
                status="tp" if (p, v) in tp else "fp",
            )
            for p, v in by_predicate(gen_e.facts)
        ]
        get_cd(compact(gold_e.class_uri)).matched.append(
            EntityPairDiff(gold_facts=gold_side, generated_facts=gen_side)
        )

    for e in match.unmatched_gold:
        facts = [type_row(e.class_uri, "fn")] + [
            FactDiff(predicate=compact(p), value=str(v)[:200], status="fn")
            for p, v in by_predicate(e.facts)
        ]
        get_cd(compact(e.class_uri)).unmatched_gold.append(facts)

    for e in match.unmatched_generated:
        facts = [type_row(e.class_uri, "fp")] + [
            FactDiff(predicate=compact(p), value=str(v)[:200], status="fp")
            for p, v in by_predicate(e.facts)
        ]
        get_cd(compact(e.class_uri)).unmatched_generated.append(facts)

    return RunDiff(
        **base,
        class_diffs=sorted(by_class.values(), key=lambda c: c.class_uri),
        relation_diffs=_relation_diffs(
            match, gold_relations, generated_relations, compact
        ),
    )


def _relation_diffs(
    match: MatchResult,
    gold_relations: list[CanonicalRelation],
    generated_relations: list[CanonicalRelation],
    compact,
) -> list[RelationDiff]:
    """Score object-property statements exactly as triple_metrics._relation_fact_counts does.

    A relation is only comparable when both endpoints matched; the generated side is
    remapped onto gold keys first. A relation touching an unmatched entity cannot
    correspond to anything on the other side and is an error outright.
    """
    matched_gold_keys = {gold.key for gold, _ in match.matched_pairs}
    generated_to_gold = {gen.key: gold.key for gold, gen in match.matched_pairs}

    def row(triple: tuple[str, str, str], status: str) -> RelationDiff:
        s, p, o = triple
        return RelationDiff(
            subject=compact(s),
            predicate=compact(p),
            object=compact(o),
            status=status,  # pyright: ignore[reportArgumentType]
        )

    diffs: list[RelationDiff] = []
    gold_set: set[tuple[str, str, str]] = set()
    for r in gold_relations:
        triple = (r.subject_key, r.predicate, r.object_key)
        if r.subject_key in matched_gold_keys and r.object_key in matched_gold_keys:
            gold_set.add(triple)
        else:
            diffs.append(row(triple, "fn"))

    generated_set: set[tuple[str, str, str]] = set()
    for r in generated_relations:
        subj = generated_to_gold.get(r.subject_key)
        obj = generated_to_gold.get(r.object_key)
        if subj is not None and obj is not None:
            generated_set.add((subj, r.predicate, obj))
        else:
            diffs.append(row((r.subject_key, r.predicate, r.object_key), "fp"))

    diffs += [row(t, "tp") for t in sorted(gold_set & generated_set)]
    diffs += [row(t, "fn") for t in sorted(gold_set - generated_set)]
    diffs += [row(t, "fp") for t in sorted(generated_set - gold_set)]
    return diffs
