"""Explicit filesystem inputs for the otherwise pure configuration API."""
from pathlib import Path
import re

from orchestration.laneconf.schema import ConfigError


def read_text(path):
    """Read without universal-newline conversion, matching Bash read -r."""
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"missing conf: {path}")
    try:
        with path.open(encoding="utf-8", newline="") as stream:
            return stream.read()
    except (OSError, UnicodeError) as exc:
        raise ConfigError(f"cannot read conf: {path}") from exc


def read_tracks(directory):
    """Read track names only from the caller's explicit checkout directory."""
    return tuple(sorted(path.stem for path in Path(directory).glob("*.sh")
                        if path.is_file() and re.fullmatch(r"[a-z0-9_]+", path.stem)))
