from .models import CanonicalRelation, EvaluationMetrics, MatchResult


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return precision, recall, f1


def _entity_fact_counts(match: MatchResult) -> tuple[int, int, int]:
    # rdf:type is implicitly TP for every matched pair (matching requires equal class_uri).
    # Unmatched entities count all their facts (rdf:type + literals) as FN (gold) / FP (generated).
    tp = fp = fn = 0

    for gold_entity, generated_entity in match.matched_pairs:
        tp += 1  # rdf:type, always agrees within a matched pair
        gold_facts = gold_entity.facts
        gen_facts = generated_entity.facts
        tp += len(gold_facts & gen_facts)
        fn += len(gold_facts - gen_facts)
        fp += len(gen_facts - gold_facts)

    for entity in match.unmatched_gold:
        fn += 1 + len(entity.facts)
    for entity in match.unmatched_generated:
        fp += 1 + len(entity.facts)

    return tp, fp, fn


def _relation_fact_counts(
    match: MatchResult,
    gold_relations: list[CanonicalRelation],
    generated_relations: list[CanonicalRelation],
) -> tuple[int, int, int]:
    # Relations touching an unmatched entity can never correspond to anything in
    # the other graph, so they're counted directly as FN/FP without further comparison.
    matched_gold_keys = {gold.key for gold, _ in match.matched_pairs}
    generated_to_gold_key = {
        generated.key: gold.key for gold, generated in match.matched_pairs
    }

    gold_set: set[tuple[str, str, str]] = set()
    fn = 0
    for r in gold_relations:
        if r.subject_key in matched_gold_keys and r.object_key in matched_gold_keys:
            gold_set.add((r.subject_key, r.predicate, r.object_key))
        else:
            fn += 1

    generated_set: set[tuple[str, str, str]] = set()
    fp = 0
    for r in generated_relations:
        subj = generated_to_gold_key.get(r.subject_key)
        obj = generated_to_gold_key.get(r.object_key)
        if subj is not None and obj is not None:
            generated_set.add((subj, r.predicate, obj))
        else:
            fp += 1

    tp = len(gold_set & generated_set)
    fn += len(gold_set - generated_set)
    fp += len(generated_set - gold_set)

    return tp, fp, fn


def compute_metrics(
    match: MatchResult,
    gold_relations: list[CanonicalRelation],
    generated_relations: list[CanonicalRelation],
) -> EvaluationMetrics:
    e_tp, e_fp, e_fn = _entity_fact_counts(match)
    r_tp, r_fp, r_fn = _relation_fact_counts(match, gold_relations, generated_relations)

    tp, fp, fn = e_tp + r_tp, e_fp + r_fp, e_fn + r_fn

    precision, recall, f1 = _prf(tp, fp, fn)
    # Accuracy is deliberately not reported. It needs a count of true negatives —
    # statements correctly not made — and over an open-world RDF graph the object
    # position is an unbounded literal space, so that set is not enumerable.

    return EvaluationMetrics(
        tp=tp,
        fp=fp,
        fn=fn,
        precision=precision,
        recall=recall,
        f1=f1,
        entities_matched=len(match.matched_pairs),
        entities_unmatched_gold=len(match.unmatched_gold),
        entities_unmatched_generated=len(match.unmatched_generated),
    )
