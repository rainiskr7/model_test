"""Build publication sidecars from existing artifacts without re-inference."""

from __future__ import annotations

import os
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from .adapters import ADAPTERS, adapt_source
from .schema import (
    PublishStatus,
    SCHEMA_VERSION,
    sidecar_json,
    sidecar_path,
    sha256_file,
    validate_sidecar,
)


ORIGINAL_NAMES = {"results.json", "summary.json", "run_config.json"}


def discover_sources(base: Path) -> list[Path]:
    results = base / "results"
    if not results.exists():
        return []
    sources: list[Path] = []
    for path in results.rglob("*"):
        if "_derived" in path.parts:
            continue
        if path.is_dir() and path.name in ADAPTERS:
            sources.append(path)
        elif path.is_file() and path.suffix == ".jsonl" and path.parent.name == "kreta":
            sources.append(path)
    return sorted(sources, key=lambda path: path.as_posix())


def derived_sidecar_path(source: Path) -> Path:
    source = Path(source)
    source_dir = source.parent if source.suffix == ".jsonl" else source
    return sidecar_path(source_dir, source.stem if source.suffix == ".jsonl" else None)


def _relative(path: Path, base: Path) -> str:
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _identity(source_dir: Path, base: Path) -> tuple[str, str]:
    try:
        rel = source_dir.relative_to(base / "results")
        return rel.parts[0], rel.parts[1]
    except (ValueError, IndexError):
        return source_dir.parents[3].name, source_dir.parents[2].name


def derive_source(source: Path, base: Path) -> tuple[Path, dict[str, Any]]:
    """Derive one sidecar in memory.

    This is the public entry point future runners can call after atomically
    completing their native artifacts.  It performs no writes by itself.
    """

    source = Path(source)
    base = Path(base)
    adapted = adapt_source(source)
    source_dir: Path = adapted.pop("source_dir")
    source_files: list[Path] = adapted.pop("source_files")
    model_dir, session = _identity(source_dir, base)
    artifacts = []
    for path in source_files:
        if path.exists() and path.is_file():
            artifacts.append({"path": _relative(path, base), "sha256": sha256_file(path)})
    result = {
        "schema_version": SCHEMA_VERSION,
        "model": adapted.pop("model") or model_dir,
        "session": session,
        "source": {
            "unit": _relative(source, base),
            "artifacts": artifacts,
        },
        **adapted,
    }
    out_path = sidecar_path(source_dir, source.stem if source.suffix == ".jsonl" else None)
    return out_path, result


def native_sidecar_from_source(source: Path, base: Path) -> tuple[Path, dict[str, Any]]:
    """Revalidate completed runner artifacts and promote a clean legacy result to NATIVE."""

    out_path, sidecar = derive_source(source, base)
    sidecar["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    if sidecar["status"] == PublishStatus.LEGACY_REVALIDATED:
        sidecar["status"] = PublishStatus.NATIVE
        sidecar["publishable"] = True
    return out_path, sidecar


def rejected_sidecar_from_source(
    source: Path,
    base: Path,
    reason: str,
) -> tuple[Path, dict[str, Any]]:
    """Build a fail-closed sidecar for an explicit runner failure."""

    out_path, sidecar = derive_source(source, base)
    sidecar["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    sidecar["status"] = PublishStatus.REJECTED
    sidecar["publishable"] = False
    sidecar["failures"] = list(sidecar.get("failures") or []) + [reason]
    return out_path, sidecar


def native_sidecar_from_records(
    source: Path,
    base: Path,
    records: Iterable[dict[str, Any]],
    *,
    benchmark_id: str,
    response_field: str = "response",
    expected_count: int | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Build a NATIVE sidecar and assert it used the same raw record aggregation."""

    from .adapters import summarize_records

    aggregate = summarize_records(
        benchmark_id,
        records,
        response_field=response_field,
        expected_count=expected_count,
    )
    out_path, sidecar = native_sidecar_from_source(source, base)
    for key in ("attempted", "measured", "errored", "unresolved", "correct_measured"):
        if key in sidecar.get("counts", {}) and sidecar["counts"].get(key) != aggregate["counts"].get(key):
            raise ValueError(f"native sidecar aggregation mismatch: {key}")
    return out_path, sidecar


def preflight_kreta_source(source: Path, base: Path) -> tuple[bool, list[str]]:
    """Validate a KRETA checkpoint before upstream evaluate.py can see it."""

    from .adapters import EXPECTED_COUNTS, summarize_records

    source = Path(source)
    rows: list[dict[str, Any]] = []
    failures: list[str] = []
    try:
        with source.open(encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError("JSONL row is not an object")
                rows.append(value)
    except Exception as exc:
        failures.append(f"JSONL 읽기 실패: {type(exc).__name__}")
    aggregate = summarize_records("kreta", rows, expected_count=EXPECTED_COUNTS["kreta"])
    failures.extend(aggregate["publish_status"]["failures"])
    ids = [row.get("id") for row in rows]
    if any(item_id is None for item_id in ids) or len(set(ids)) != len(ids):
        failures.append("id가 누락되었거나 중복됨")
    return not failures, failures


def write_sidecar(path: Path, sidecar: dict[str, Any]) -> None:
    """Atomically write a validated sidecar below ``_derived``."""

    path = Path(path)
    if path.parent.name != "_derived":
        raise ValueError("publication sidecars must be written below _derived")
    payload = sidecar_json(sidecar)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, path)


def existing_native_sidecar(path: Path) -> dict[str, Any] | None:
    """Return a valid existing NATIVE sidecar, never trusting status alone."""

    try:
        sidecar = json.loads(Path(path).read_text(encoding="utf-8"))
        validate_sidecar(sidecar)
    except Exception:
        return None
    return sidecar if sidecar.get("status") == PublishStatus.NATIVE else None


def derive_all(
    base: Path,
    *,
    write: bool = False,
    force: bool = False,
    on_native_skip: Callable[[Path, dict[str, Any]], None] | None = None,
    on_native_overwrite: Callable[[Path, dict[str, Any]], None] | None = None,
) -> list[tuple[Path, dict[str, Any]]]:
    """Derive legacy sidecars without downgrading valid NATIVE records by default."""

    derived: list[tuple[Path, dict[str, Any]]] = []
    for source in discover_sources(base):
        path = derived_sidecar_path(source)
        native = existing_native_sidecar(path) if path.exists() else None
        if native is not None and not force:
            if on_native_skip is not None:
                on_native_skip(path, native)
            continue
        if native is not None and on_native_overwrite is not None:
            on_native_overwrite(path, native)
        item = derive_source(source, base)
        derived.append(item)
        if write:
            write_sidecar(*item)
    return derived


def original_artifact_manifest(base: Path) -> dict[str, str]:
    """SHA-256 manifest of contract-protected original result artifacts."""

    manifest: dict[str, str] = {}
    results = Path(base) / "results"
    if not results.exists():
        return manifest
    for path in results.rglob("*"):
        if not path.is_file() or "_derived" in path.parts:
            continue
        if path.name in ORIGINAL_NAMES or path.suffix == ".jsonl":
            manifest[_relative(path, Path(base))] = sha256_file(path)
    return manifest
