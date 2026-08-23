"""Type-based record outcome classification (contract section 1)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .schema import RecordClass

_MISSING = object()


def classify_record(record: Mapping[str, Any], response_field: str = "response") -> RecordClass:
    """Classify one inference record without inspecting response text.

    A string that happens to contain ``{'error': ...}`` remains MEASURED.
    KOFFVQA uses ``prediction`` rather than ``response`` and passes that field
    explicitly.
    """

    if record.get("error"):
        return RecordClass.ERRORED
    response = record.get(response_field, _MISSING)
    if isinstance(response, Mapping):
        return RecordClass.ERRORED if response.get("error") else RecordClass.UNRESOLVED
    if isinstance(response, str):
        return RecordClass.MEASURED
    return RecordClass.UNRESOLVED


# Contract wording and small callers commonly use ``classify(record)``.
classify = classify_record
