"""Build publication sidecars from existing artifacts without re-inference."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterable

from .adapters import ADAPTERS, adapt_source
from .schema import SCHEMA_VERSION, sidecar_json, sidecar_path, sha256_file


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


def derive_all(base: Path, *, write: bool = False) -> list[tuple[Path, dict[str, Any]]]:
    derived = [derive_source(source, base) for source in discover_sources(base)]
    if write:
        for path, sidecar in derived:
            write_sidecar(path, sidecar)
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
