#!/usr/bin/env python3
"""
Queue several experiment YAMLs back-to-back so a whole sweep runs unattended.

No scheduler is involved and none is needed. ExperimentManager dispatches into a
ThreadPoolExecutor whose work queue is unbounded, so every run submitted beyond the
max_concurrent workers simply waits its turn in FIFO order. Submitting three configs
one after another therefore produces a single queue that drains overnight — the second
experiment starts the moment the first one's last run frees a worker.

Usage:
    python scripts/submit-experiments.py                  # every *.yaml in the folder
    python scripts/submit-experiments.py acled adsb       # only matching names
    python scripts/submit-experiments.py --dry-run        # expand + count, queue nothing
"""

import argparse
import collections
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = Path(__file__).parent.parent
CONFIGS = BASE / "data" / "experiment-configs"

# docker-compose publishes the app's port 8000 on host port 8420.
API_BASE = os.getenv("API_URL", "http://localhost:8420").rstrip("/")
API = f"{API_BASE}/api/experiments"


def post(endpoint: str, payload: dict) -> list:
    request = urllib.request.Request(
        f"{API}/{endpoint}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def status() -> int:
    """Print a per-experiment status breakdown of everything currently in the store."""
    try:
        with urllib.request.urlopen(f"{API}/runs", timeout=30) as response:
            runs = json.load(response)
    except urllib.error.URLError as error:
        print(f"Cannot reach {API} — is the API up? ({error})", file=sys.stderr)
        return 1

    by_experiment: dict[str, collections.Counter] = collections.defaultdict(
        collections.Counter
    )
    for run in runs:
        name = run.get("config", {}).get("experiment_name") or "(unnamed)"
        by_experiment[name][run.get("status", "?")] += 1

    order = ["completed", "failed", "queued", "mapping", "extracting", "cancelled"]
    for name, counts in sorted(by_experiment.items()):
        parts = [f"{s}={counts[s]}" for s in order if counts[s]]
        parts += [f"{s}={c}" for s, c in counts.items() if s not in order]
        print(f"  {name:28s} {sum(counts.values()):4d} runs   {'  '.join(parts)}")
    if not by_experiment:
        print("  no runs in the store")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("filters", nargs="*", help="substrings of config filenames")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="expand the matrices and report counts without queueing",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="show per-experiment run counts by status, then exit",
    )
    args = parser.parse_args()

    if args.status:
        return status()

    files = sorted(CONFIGS.glob("*.yaml"))
    if args.filters:
        files = [f for f in files if any(x in f.name for x in args.filters)]
    files = [f for f in files if f.stat().st_size > 0]
    if not files:
        print("No non-empty configs matched.", file=sys.stderr)
        return 1

    endpoint = "preview-yaml" if args.dry_run else "submit-yaml"
    total = 0
    for path in files:
        try:
            runs = post(endpoint, {"yaml_content": path.read_text()})
        except urllib.error.HTTPError as error:
            detail = error.read().decode()[:300]
            print(f"  {path.name:28s} FAILED {error.code}: {detail}", file=sys.stderr)
            return 1
        except urllib.error.URLError as error:
            print(f"Cannot reach {API} — is the API up? ({error})", file=sys.stderr)
            return 1
        total += len(runs)
        verb = "would queue" if args.dry_run else "queued"
        print(f"  {path.name:28s} {verb} {len(runs):4d} runs")

    print(f"\n  {'TOTAL':28s} {total} runs")
    if not args.dry_run:
        print("\nThe runs share one FIFO queue and drain in submission order.")
        print("Watch:  python scripts/submit-experiments.py --status")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
