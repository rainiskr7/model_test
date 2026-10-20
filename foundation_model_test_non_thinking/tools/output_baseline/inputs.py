"""Fixed input selection and content manifests (no runtime discovery)."""

import hashlib
from pathlib import Path

KINDS = {"agent", "taubench", "functionchat", "multimodal"}


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_inputs(path):
    entries = []
    for number, line in enumerate(Path(path).read_text().splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split(maxsplit=1)
        if len(fields) != 2 or fields[0] not in KINDS:
            raise ValueError(f"inputs line {number}: expected kind results/path")
        kind, value = fields
        relative = Path(value)
        if relative.is_absolute() or ".." in relative.parts or relative.parts[0] != "results":
            raise ValueError(f"inputs line {number}: unsafe path {value}")
        entry = {"kind": kind, "path": relative.as_posix()}
        if any(item["path"] == entry["path"] for item in entries):
            raise ValueError(f"duplicate input: {value}")
        entries.append(entry)
    if {item["kind"] for item in entries} != KINDS:
        raise ValueError("inputs must cover agent, taubench, functionchat, multimodal")
    return entries


def copy_roots(entries):
    paths = {item["path"] for item in entries}
    paths.add("configs/model_identity.json")
    for item in entries:
        path = Path(item["path"])
        if item["kind"] == "multimodal" and path.name == "koffvqa_api_judge":
            paths.add((path.parent / "koffvqa").as_posix())
        if item["kind"] == "multimodal" and path.suffix == ".jsonl" and path.parent.name == "kreta":
            paths.add(path.parent.as_posix())
    return sorted(p for p in paths if not any(parent.as_posix() in paths for parent in Path(p).parents))


def file_manifest(root):
    return {p.relative_to(root).as_posix(): sha256(p)
            for p in sorted(Path(root).rglob("*")) if p.is_file()}


def validate_snapshot(snapshot):
    root = Path(snapshot["root"])
    issues = []
    for relative in snapshot["required"]:
        if not (root / relative).exists():
            issues.append(f"missing input: {relative}")
    for relative, expected in snapshot["files"].items():
        path = root / relative
        if not path.is_file():
            issues.append(f"missing input file: {relative}")
        elif sha256(path) != expected:
            issues.append(f"changed input: {relative}")
    actual = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
    issues.extend(f"unexpected input file: {path}" for path in sorted(actual - snapshot["files"].keys()))
    if not snapshot["files"]:
        issues.append("empty input snapshot")
    return issues
