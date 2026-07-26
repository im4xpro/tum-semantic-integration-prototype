"""Provenance sidecar for populate runs (REQ-PROV-FR-02).

Each populate writes one manifest per run under data/provenance/{run_id}.json,
recording every subject it created together with the source record it came from,
so the operator can trace any node back to its origin. Kept as a sidecar rather
than inflating the Run JSON, which is the run's operational record.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

_PROVENANCE_DIR = Path(__file__).parent.parent.parent.parent / "data" / "provenance"


class ProvenanceEntry(BaseModel):
    subject_uri: str
    source_record_id: str
    class_uri: str


class ProvenanceManifest(BaseModel):
    run_id: str
    source_name: str
    connector: str
    mapping_id: str
    mapping_name: str | None = None
    target_named_graph: str
    created_at: datetime
    entry_count: int
    entries: list[ProvenanceEntry]


class ProvenanceStore:
    """Reads/writes one manifest JSON per run under *provenance_dir*."""

    def __init__(self, provenance_dir: Path = _PROVENANCE_DIR):
        self._dir = provenance_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def save(self, manifest: ProvenanceManifest) -> Path:
        # Deterministic per-run path, so re-populating (same run id is new, but a
        # stale manifest for a replaced graph is simply overwritten on rewrite).
        path = self._dir / f"{manifest.run_id}.json"
        path.write_text(
            json.dumps(manifest.model_dump(mode="json"), indent=2, default=str)
        )
        return path

    def load(self, run_id: str) -> ProvenanceManifest | None:
        path = self._dir / f"{run_id}.json"
        if not path.exists():
            return None
        return ProvenanceManifest.model_validate(json.loads(path.read_text()))
