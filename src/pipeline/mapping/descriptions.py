import json
from pathlib import Path


def load_column_descriptions(source_name: str, descriptions_dir: Path) -> dict[str, str] | None:
    """
    Load a manually-authored {column_name: description} JSON for *source_name*
    from *descriptions_dir*. Returns None if no such file exists, so callers
    can fall back to a prompt without descriptions.
    """
    path = descriptions_dir / f"{source_name}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())
