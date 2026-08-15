"""Stored result-record shape helpers shared by scoring and diagnostics."""

from typing import Any, Dict


def has_repetition_records(task: Dict[str, Any]) -> bool:
    records = task.get("repetition_records")
    return isinstance(records, list) and bool(records)
