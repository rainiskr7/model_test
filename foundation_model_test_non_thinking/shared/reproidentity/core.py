"""Stable item digests and identities for recorded metadata."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable


def digest(values: Iterable[str]) -> str:
    """Hash sorted item identifiers joined by LF, keeping 16 hex digits."""
    material = "\n".join(sorted(values)).encode("utf-8")
    return hashlib.sha256(material).hexdigest()[:16]


def metadata_identity(values: Iterable[Any]) -> Any:
    """Preserve a single recorded value or distinguish conflicting values."""
    encoded = {
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for value in values
    }
    if not encoded:
        return None
    decoded = [json.loads(value) for value in sorted(encoded)]
    return decoded[0] if len(decoded) == 1 else tuple(sorted(encoded))
