"""Literal LF-delimited assignments; no whitespace or shell normalization."""
from orchestration.laneconf.schema import ConfigError


def parse(text):
    """Parse assignments, preserving values and rejecting repeated raw keys."""
    entries, seen = [], set()
    for line in text.split("\n"):
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator:
            raise ConfigError(f"expected key=value: {line}")
        if key in seen:
            raise ConfigError(f"duplicate key: {key}")
        seen.add(key)
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        entries.append((key, value))
    return entries
