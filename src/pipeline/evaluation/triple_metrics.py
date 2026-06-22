from .models import CanonicalRelation, EvaluationMetrics, MatchResult


def _entity_fact_counts(match: MatchResult) -> tuple[int, int, int]:
    """
    TP/FP/FN over entity-level facts: the rdf:type triple (implicitly TP for
    every matched pair, since matching requires equal class_uri) plus every
    literal property triple. Unmatched entities count all of their facts
    (rdf:type + literals) as FN (gold) / FP (generated).
    """
    tp = fp = fn = 0

    for gold_entity, generated_entity in match.matched_pairs:
        tp += 1  # rdf:type, always agrees within a matched pair
        for fact in gold_entity.facts:
            if fact in generated_entity.facts:
                tp += 1
            else:
                fn += 1
        for fact in generated_entity.facts:
            if fact not in gold_entity.facts:
                fp += 1

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
    """
    TP/FP/FN over object-property (relation) triples, compared via the
    matched-entity correspondence: a gold relation is only comparable if both
    its endpoints were matched to some generated entity, and vice versa.
    Relations touching an unmatched entity can never be reproduced/correspond
    to anything, so they're counted as FN/FP directly.
    """
    matched_gold_keys = {gold.key for gold, _ in match.matched_pairs}
    generated_to_gold_key = {generated.key: gold.key for gold, generated in match.matched_pairs}

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
    """
    Precision/recall/F1 over the pooled entity + relation TP/FP/FN counts, plus
    accuracy = TP/(TP+FP+FN) (Jaccard similarity between the gold and
    generated fact sets — there is no well-defined "true negative" here, so
    this is NOT the classical (TP+TN)/total accuracy).
    """
    e_tp, e_fp, e_fn = _entity_fact_counts(match)
    r_tp, r_fp, r_fn = _relation_fact_counts(match, gold_relations, generated_relations)

    tp, fp, fn = e_tp + r_tp, e_fp + r_fp, e_fn + r_fn

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    accuracy = tp / (tp + fp + fn) if (tp + fp + fn) else 0.0

    return EvaluationMetrics(
        tp=tp,
        fp=fp,
        fn=fn,
        precision=precision,
        recall=recall,
        f1=f1,
        accuracy=accuracy,
        entities_matched=len(match.matched_pairs),
        entities_unmatched_gold=len(match.unmatched_gold),
        entities_unmatched_generated=len(match.unmatched_generated),
    )
