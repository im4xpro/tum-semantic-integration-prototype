import json
from pathlib import Path
from datetime import datetime
from .models import MappingDocument

#TODO: Use a database here
class MappingStore:

    def __init__(self, storage_path: Path):
        self.storage_path = storage_path
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def save(self, mapping: MappingDocument) -> Path:
        timestamp = mapping.generation_timestamp.strftime("%Y%m%d_%H%M%S")
        model_safe = mapping.llm_model.replace(":", "-").replace("/", "-")
        filename = f"{mapping.source_name}_{model_safe}_{mapping.strategy}_{timestamp}.json"
        path = self.storage_path / filename

        with open(path, "w") as f:
            json.dump(mapping.model_dump(), f, indent=2, default=str)

        return path

    def load(self, path: Path) -> MappingDocument:
        with open(path, "r") as f:
            return MappingDocument.model_validate(json.load(f))

    def list_mappings(self, source: str | None = None) -> list[Path]:
        files = sorted(self.storage_path.glob("*.json"))
        if source:
            files = [f for f in files if f.name.startswith(source)]
        return files

    def get_latest(self, source: str) -> MappingDocument | None:
        files = self.list_mappings(source)
        if not files:
            return None
        return self.load(files[-1])

    def get_approved(self, source: str) -> MappingDocument | None:
        files = self.list_mappings(source)
        for path in reversed(files):
            mapping = self.load(path)
            if mapping.status == "approved":
                return mapping
        return None