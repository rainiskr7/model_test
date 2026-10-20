"""Read a UTF-8 JSON artifact whose top-level value must be an object."""

import json
from pathlib import Path
from typing import Any, Dict


def load_json_object(path: Path) -> Dict[str, Any]:
    """Load a JSON object, preserving decoder and filesystem errors."""
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {path}")
    return data
