"""Cohort grouping and atomic representative-run selection."""

from __future__ import annotations

from datetime import datetime
from pathlib import PurePosixPath
from typing import Any, Iterable

from .schema import PublishStatus, canonical_json, canonical_model_id


def cohort_key(sidecar: dict[str, Any]) -> tuple[str, str, str, str]:
    protocol = sidecar.get("protocol") or {}
    return (
        str(sidecar.get("benchmark_id")),
        str(sidecar.get("variant")),
        str(protocol.get("fingerprint")),
        canonical_model_id(sidecar),
    )


def _artifact_signature(sidecar: dict[str, Any]) -> tuple[tuple[str, str], ...] | None:
    """Return a path-independent signature for an exact copied run."""

    source = sidecar.get("source") or {}
    artifacts = source.get("artifacts") if isinstance(source, dict) else None
    if not isinstance(artifacts, list) or not artifacts:
        return None
    unit = PurePosixPath(str(source.get("unit") or ""))
    source_dir = unit.parent if unit.suffix else unit
    signature: list[tuple[str, str]] = []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            return None
        raw_path, sha256 = artifact.get("path"), artifact.get("sha256")
        if not isinstance(raw_path, str) or not raw_path or not isinstance(sha256, str) or not sha256:
            return None
        path = PurePosixPath(raw_path)
        try:
            role = path.relative_to(source_dir).as_posix()
        except ValueError:
            # A valid sidecar normally records artifacts below source.unit.
            # Retain the full path when it does not so unrelated roles cannot
            # collapse merely because their bytes match.
            role = path.as_posix()
        signature.append((role, sha256))
    return tuple(sorted(signature))


def _source_unit(sidecar: dict[str, Any]) -> str:
    source = sidecar.get("source") or {}
    return str(source.get("unit") or "") if isinstance(source, dict) else ""


def _copy_priority(sidecar: dict[str, Any]) -> tuple[bool, bool, int, str]:
    unit = _source_unit(sidecar)
    has_bad_suffix = any(part.endswith(".bad") for part in unit.split("/"))
    is_not_native = sidecar.get("status") != PublishStatus.NATIVE.value
    return is_not_native, has_bad_suffix, len(unit), unit


def _measurement_payload(sidecar: dict[str, Any]) -> str:
    """Canonical payload whose equality permits exact-copy folding."""

    return canonical_json({
        "counts": sidecar.get("counts"),
        "metrics": sidecar.get("metrics"),
        "provisional": sidecar.get("provisional"),
    })


def _session_identity(sidecar: dict[str, Any]) -> str:
    """Normalize only the explicit copied-directory ``.bad`` suffix."""

    session = str(sidecar.get("session") or "")
    return session[:-4] if session.endswith(".bad") else session


def _fold_exact_copies(
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    groups: dict[tuple[str, tuple[tuple[str, str], ...]], list[dict[str, Any]]] = {}
    unique_without_signature: list[dict[str, Any]] = []
    for candidate in candidates:
        signature = _artifact_signature(candidate)
        if signature is None:
            unique_without_signature.append(candidate)
        else:
            groups.setdefault((_session_identity(candidate), signature), []).append(candidate)
    kept = list(unique_without_signature)
    folded: list[dict[str, Any]] = []
    for (_, signature), signature_copies in groups.items():
        payload_groups: dict[str, list[dict[str, Any]]] = {}
        for candidate in signature_copies:
            payload_groups.setdefault(_measurement_payload(candidate), []).append(candidate)
        for copies in payload_groups.values():
            copies.sort(key=_copy_priority)
            winner, duplicates = copies[0], copies[1:]
            kept.append(winner)
            if duplicates:
                folded.append({
                    "artifact_signature": [list(pair) for pair in signature],
                    "kept": _source_unit(winner),
                    "folded": [_source_unit(item) for item in duplicates],
                })
    kept.sort(key=_source_unit)
    folded.sort(key=lambda item: item["kept"])
    return kept, folded


def _with_selection_metadata(
    representative: dict[str, Any],
    candidates: list[dict[str, Any]],
    folded: list[dict[str, Any]],
    ineligible: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    selected = dict(representative)
    selected["_selection"] = {
        "cohort_runs": candidates,
        "folded_duplicates": folded,
        # Only runs that lost representative eligibility to a dated rival.  A
        # lone undated run represents its own cohort, so it is not listed here.
        "undated_candidates": ineligible or [],
    }
    return selected


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
    for key, original_candidates in cohorts.items():
        candidates, folded = _fold_exact_copies(original_candidates)
        if len(candidates) == 1:
            selected.append(_with_selection_metadata(candidates[0], candidates, folded))
            continue
        dated = [(stamp, candidate) for candidate in candidates if (stamp := _timestamp(candidate.get("completed_at_utc"))) is not None]
        undated = [candidate for candidate in candidates if _timestamp(candidate.get("completed_at_utc")) is None]
        # A run without a completion time cannot be shown to be the most recent,
        # so it is not eligible to *represent* a cohort that also holds a dated
        # run — but it stays in cohort_runs and still counts toward the
        # reproducibility spread.  Every reproduction of a legacy baseline mixes
        # the two, and dropping the whole model from the table would lose a valid
        # measurement to say nothing new.
        ineligible: list[dict[str, Any]] = []
        if dated and undated:
            ineligible, undated = undated, []
        if undated:
            ambiguous.append({
                "key": key, "candidates": candidates, "folded_duplicates": folded,
                "reason": "신뢰 가능한 완료 시각으로 결정할 수 없음",
            })
            continue
        latest = max(stamp for stamp, _ in dated)
        latest_candidates = [candidate for stamp, candidate in dated if stamp == latest]
        if len(latest_candidates) != 1:
            ambiguous.append({
                "key": key, "candidates": candidates, "folded_duplicates": folded,
                "reason": "동일한 최신 완료 시각 후보가 둘 이상",
            })
            continue
        selected.append(
            _with_selection_metadata(latest_candidates[0], candidates, folded, ineligible)
        )
    selected.sort(key=cohort_key)
    ambiguous.sort(key=lambda item: item["key"])
    return selected, ambiguous
