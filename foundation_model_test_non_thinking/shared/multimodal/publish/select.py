"""Cohort grouping and atomic representative-run selection."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable


def cohort_key(sidecar: dict[str, Any]) -> tuple[str, str, str, str]:
    protocol = sidecar.get("protocol") or {}
    return (
        str(sidecar.get("benchmark_id")),
        str(sidecar.get("variant")),
        str(protocol.get("fingerprint")),
        str(sidecar.get("model")),
    )


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def select_representatives(
    sidecars: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Select whole-run representatives without score/name/denominator tie-breaks."""

    cohorts: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    for sidecar in sidecars:
        if sidecar.get("publishable") is True:
            cohorts.setdefault(cohort_key(sidecar), []).append(sidecar)
    selected: list[dict[str, Any]] = []
    ambiguous: list[dict[str, Any]] = []
    for key, candidates in cohorts.items():
        if len(candidates) == 1:
            selected.append(candidates[0])
            continue
        dated = [(stamp, candidate) for candidate in candidates if (stamp := _timestamp(candidate.get("completed_at_utc"))) is not None]
        undated = [candidate for candidate in candidates if _timestamp(candidate.get("completed_at_utc")) is None]
        if dated and undated:
            ambiguous.append({"key": key, "candidates": candidates, "reason": "완료 시각이 있는 후보와 없는 후보가 섞여 있음"})
            continue
        if undated:
            ambiguous.append({"key": key, "candidates": candidates, "reason": "신뢰 가능한 완료 시각으로 결정할 수 없음"})
            continue
        latest = max(stamp for stamp, _ in dated)
        latest_candidates = [candidate for stamp, candidate in dated if stamp == latest]
        if len(latest_candidates) != 1:
            ambiguous.append({"key": key, "candidates": candidates, "reason": "동일한 최신 완료 시각 후보가 둘 이상"})
            continue
        selected.append(latest_candidates[0])
    selected.sort(key=cohort_key)
    ambiguous.sort(key=lambda item: item["key"])
    return selected, ambiguous
