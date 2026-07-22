#!/usr/bin/env python3
"""
Evaluate every completed run in an experiment against a gold standard.

Usage:
    PYTHONPATH=src python scripts/evaluate-experiment.py <experiment_name> \
        [--gold data/gold_standard/<source>.gold.json] \
        [--output-dir data/output]

Writes <output-dir>/<experiment_name>_evaluation.{csv,md} and prints the
table plus a best/worst-by-F1 summary. Requires GraphDB to be running and
reachable, and at least one completed run for the experiment.
"""

import argparse
import logging
import sys
from pathlib import Path

logging.getLogger("rdflib").setLevel(logging.ERROR)

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "src"))

from pipeline.evaluation.report import (  # noqa: E402
    evaluate_experiment,
    resolve_source_name,
    write_report,
)

SCHEMAS_DIR = BASE / "data" / "schemas"
ONTOLOGY_PATH = BASE / "data" / "ontology" / "thesis_ontology.ttl"
GOLD_STANDARD_DIR = BASE / "data" / "gold_standard"
DEFAULT_OUTPUT_DIR = BASE / "data" / "output"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("experiment_name")
    parser.add_argument(
        "--gold",
        type=Path,
        help="Gold MappingDocument JSON (default: inferred from source_name)",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    if args.gold:
        gold_path = args.gold
    else:
        try:
            source_name = resolve_source_name(args.experiment_name)
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)
        gold_path = GOLD_STANDARD_DIR / f"{source_name}.gold.json"

    print(f"\n{'─' * 64}")
    print(f"  Experiment : {args.experiment_name}")
    print(f"  Gold       : {gold_path.relative_to(BASE)}")
    print(f"{'─' * 64}\n")

    df = evaluate_experiment(
        experiment_name=args.experiment_name,
        gold_mapping_path=gold_path,
        schemas_dir=SCHEMAS_DIR,
        ontology_path=ONTOLOGY_PATH,
    )

    if df.empty:
        print(f"No completed runs found for experiment '{args.experiment_name}'.")
        return

    print(df.to_markdown(index=False))

    csv_path, md_path = write_report(df, args.output_dir, args.experiment_name)
    print(f"\n  CSV  → {csv_path.relative_to(BASE)}")
    print(f"  MD   → {md_path.relative_to(BASE)}")

    scored = df[df["error"].isna()] if "error" in df.columns else df
    if not scored.empty:
        best = scored.loc[scored["f1"].idxmax()]
        worst = scored.loc[scored["f1"].idxmin()]
        print(
            f"\n  Best  (F1={best['f1']:.3f}): {best['provider']}/{best['llm_model']}, "
            f"{best['strategy']}, {best['ontology_format']}"
        )
        print(
            f"  Worst (F1={worst['f1']:.3f}): {worst['provider']}/{worst['llm_model']}, "
            f"{worst['strategy']}, {worst['ontology_format']}"
        )
    print()


if __name__ == "__main__":
    main()
