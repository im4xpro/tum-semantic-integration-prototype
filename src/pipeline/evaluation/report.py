from pathlib import Path

import pandas as pd
from rdflib import URIRef

from pipeline.extraction.models import ExtractionResult
from pipeline.graph.graphdb_client import GraphDBClient
from pipeline.graph.rdf_serializer import build_namespaces
from pipeline.mapping.models import MappingDocument
from pipeline.runner.models import Run, RunStatus
from pipeline.runner.pipeline_runner import build_graphdb_config
from pipeline.runner.run_store import RunStore

from .gold_graph import build_gold_extraction_results
from .models import EvaluationResult
from .signatures import entities_from_extraction, entities_from_graph, match_entities
from .triple_metrics import compute_metrics


def evaluate_run(
    run: Run,
    gold_results: list[ExtractionResult],
    gold_mapping: MappingDocument,
    gold_property_ranges: dict[str, URIRef],
) -> EvaluationResult:
    base = {
        "run_id": run.id,
        "experiment_name": run.config.experiment_name,
        "provider": run.config.provider,
        "llm_model": run.config.llm_model,
        "strategy": run.config.strategy,
        "ontology_format": run.config.ontology_format,
        "include_descriptions": run.config.include_descriptions,
    }

    if run.status != RunStatus.completed or not run.named_graph:
        return EvaluationResult(
            **base, error=f"run status is '{run.status}', no named graph to evaluate"
        )

    try:
        client = GraphDBClient(build_graphdb_config(run.config))
        generated_graph = client.construct_named_graph(run.named_graph)
    except Exception as e:
        return EvaluationResult(**base, error=f"failed to fetch generated graph: {e}")

    gold_namespaces = build_namespaces(gold_mapping)
    gold_entities, gold_relations = entities_from_extraction(
        gold_results, gold_namespaces, gold_property_ranges
    )
    generated_entities, generated_relations = entities_from_graph(generated_graph)

    match = match_entities(gold_entities, generated_entities)
    metrics = compute_metrics(match, gold_relations, generated_relations)

    return EvaluationResult(
        **base,
        precision=metrics.precision,
        recall=metrics.recall,
        f1=metrics.f1,
        jaccard=metrics.jaccard,
        tp=metrics.tp,
        fp=metrics.fp,
        fn=metrics.fn,
        entities_matched=metrics.entities_matched,
        entities_unmatched_gold=metrics.entities_unmatched_gold,
        entities_unmatched_generated=metrics.entities_unmatched_generated,
    )


def resolve_source_name(experiment_name: str, run_store: RunStore | None = None) -> str:
    # The gold standard is keyed by source_name, not experiment_name — the same
    # source can be evaluated across many differently-named experiments.
    store = run_store or RunStore()
    runs = [
        r
        for r in store.list_by_experiment(experiment_name)
        if r.status == RunStatus.completed
    ]
    if not runs:
        raise ValueError(f"No completed runs found for experiment '{experiment_name}'")

    source_names = {r.config.source_name for r in runs}
    if len(source_names) > 1:
        raise ValueError(
            f"Experiment '{experiment_name}' has runs for multiple sources {source_names} "
            "— an evaluation run expects a single gold standard per experiment."
        )
    return source_names.pop()


def evaluate_experiment(
    experiment_name: str,
    gold_mapping_path: Path,
    schemas_dir: Path,
    ontology_path: Path,
    run_store: RunStore | None = None,
) -> pd.DataFrame:
    store = run_store or RunStore()
    runs = [
        r
        for r in store.list_by_experiment(experiment_name)
        if r.status == RunStatus.completed
    ]

    gold_results, gold_mapping, gold_property_ranges = build_gold_extraction_results(
        gold_mapping_path, schemas_dir, ontology_path
    )

    rows = [
        evaluate_run(run, gold_results, gold_mapping, gold_property_ranges).model_dump()
        for run in runs
    ]
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(
            [
                "provider",
                "llm_model",
                "strategy",
                "ontology_format",
                "include_descriptions",
            ]
        )
    return df


def write_report(
    df: pd.DataFrame, output_dir: Path, experiment_name: str
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / f"{experiment_name}_evaluation.csv"
    md_path = output_dir / f"{experiment_name}_evaluation.md"
    df.to_csv(csv_path, index=False)
    md_path.write_text(df.to_markdown(index=False))
    return csv_path, md_path
