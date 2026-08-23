"""Publication sidecar schema, canonical serialization, and invariants."""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping


SCHEMA_VERSION = 1
SIDECAR_SUFFIX = ".publish.json"
KRETA_ANSWER_PARSER_VERSION = "kreta-response-choice-v2"
KRETA_ANSWER_PARSER_SPEC = {
    "normalization": "strip, remove markdown emphasis, then Unicode uppercase",
    "selection": "last explicit answer marker; short whole response; restricted last line",
    "explicit_patterns": [
        r"(?:FINAL\s+)?ANSWER\s*(?:IS|[:：])\s*(?:OPTION\s*)?[\(\[\{]?\s*([A-D])(?=\s|[\)\]\}.:,]|$)",
        r"(?:THE\s+)?CORRECT\s+(?:ANSWER|MATCH|CHOICE|OPTION)\s*(?:IS|[:：])?\s*(?:OPTION\s*)?[\(\[\{]?\s*([A-D])(?=\s|[\)\]\}.:,]|$)",
        r"(?:정답|답)\s*(?:은|는|이|가|[:：])\s*(?:선택지\s*)?[\(\[\{]?\s*([A-D])(?=\s|[\)\]\}.:,]|$)",
        r"(?:정답|답)\s+(?:OPTION|선택지)?\s*[\(\[\{]?\s*([A-D])(?=\s|[\)\]\}.:,]|$)",
        r"\bOPTION\s*[:：]?\s*([A-D])(?=\s|[\)\]\}.:,]|$)",
        r"\\BOXED\s*\{\s*([A-D])\s*\}",
    ],
    "short_max_compact_chars": 5,
    "short_pattern": r"[\(\[\{]?([A-D])[\)\]\}.:,!\-]*",
    "last_line_pattern": r"[\(\[\{]?\s*([A-D])\s*[\)\]\}]?\s*(?:번|[\.:：-].*)?",
}


class RecordClass(str, Enum):
    MEASURED = "MEASURED"
    ERRORED = "ERRORED"
    UNRESOLVED = "UNRESOLVED"


class PublishStatus(str, Enum):
    NATIVE = "NATIVE"
    LEGACY_REVALIDATED = "LEGACY_REVALIDATED"
    REJECTED = "REJECTED"
    INSUFFICIENT_PROVENANCE = "INSUFFICIENT_PROVENANCE"
    UNSCORED = "UNSCORED"

    @property
    def publishable(self) -> bool:
        return self in {self.NATIVE, self.LEGACY_REVALIDATED}


STATUS_PRIORITY = {
    PublishStatus.NATIVE: 0,
    PublishStatus.LEGACY_REVALIDATED: 1,
    PublishStatus.INSUFFICIENT_PROVENANCE: 2,
    PublishStatus.UNSCORED: 3,
    PublishStatus.REJECTED: 4,
}

COMPARISON_CRITICAL_UNKNOWN = {
    "dataset_item_digest",
    "dataset_revision",
    "mode",
    "split",
    "category_filter",
    "limit",
}

# These fields remain in the sidecar as provenance, but do not define the
# evaluated item set.  Repository/revision changes can be unrelated to data.
FINGERPRINT_INFORMATIONAL_RECORDED = {
    "dataset_provenance",
    "dataset_git_commit",
    "dataset_huggingface_id",
    "dataset_revision",
    "dataset_revision_source",
    "dataset_git_repo",
    "git_commit",
    "huggingface_id",
    "revision",
    # Binds a KOFFVQA judge run to one prediction artifact, but is model
    # output rather than evaluation protocol and therefore must not split a
    # cohort per model.
    "prediction_sha256",
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


KRETA_ANSWER_PARSER_HASH = sha256_bytes(
    canonical_json(KRETA_ANSWER_PARSER_SPEC).encode("utf-8")
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def validate_artifact_integrity(sidecar: Mapping[str, Any], base: Path) -> None:
    """Verify every source artifact recorded by a sidecar against disk.

    Schema validation alone cannot detect a raw artifact changed after a
    NATIVE sidecar was written.  Publication and passive derive both call
    this function before trusting such a sidecar.
    """

    source = sidecar.get("source")
    artifacts = source.get("artifacts") if isinstance(source, Mapping) else None
    if not isinstance(artifacts, list) or not artifacts:
        raise ValueError("source.artifacts must be a non-empty list")
    root = Path(base).resolve()
    for artifact in artifacts:
        if not isinstance(artifact, Mapping):
            raise ValueError("source artifact must be an object")
        raw_path = artifact.get("path")
        expected = artifact.get("sha256")
        if not isinstance(raw_path, str) or not isinstance(expected, str):
            raise ValueError("source artifact path/sha256 is required")
        candidate = Path(raw_path)
        if candidate.is_absolute():
            resolved = candidate.resolve()
        else:
            resolved = (root / candidate).resolve()
            try:
                resolved.relative_to(root)
            except ValueError as exc:
                raise ValueError(f"source artifact escapes base: {raw_path}") from exc
        if not resolved.is_file():
            raise ValueError(f"source artifact missing: {raw_path}")
        if sha256_file(resolved) != expected:
            raise ValueError(f"source artifact sha256 mismatch: {raw_path}")


def dataset_item_digest(items: Iterable[str]) -> str:
    """Return the short identity digest of sorted artifact item keys."""

    material = "\n".join(sorted(items)).encode("utf-8")
    return hashlib.sha256(material).hexdigest()[:16]


def protocol_fingerprint(recorded: Mapping[str, Any], inferred: Mapping[str, Any]) -> str:
    """Hash protocol facts only; model and run identifiers are intentionally absent."""

    comparable_recorded = {
        key: value
        for key, value in recorded.items()
        if key not in FINGERPRINT_INFORMATIONAL_RECORDED
    }
    return sha256_bytes(
        canonical_json({"recorded": comparable_recorded, "inferred": inferred}).encode("utf-8")
    )


def make_protocol(
    recorded: Mapping[str, Any],
    inferred: Mapping[str, Any],
    unknown: list[str] | tuple[str, ...],
) -> dict[str, Any]:
    unknown_sorted = sorted(set(unknown))
    return {
        "fingerprint": protocol_fingerprint(recorded, inferred),
        "recorded": dict(recorded),
        "inferred": dict(inferred),
        "unknown": unknown_sorted,
        "complete": not unknown_sorted,
    }


def strongest_status(*statuses: PublishStatus) -> PublishStatus:
    if not statuses:
        return PublishStatus.NATIVE
    return max(statuses, key=STATUS_PRIORITY.__getitem__)


def sidecar_path(source_dir: Path, source_name: str | None = None) -> Path:
    name = "publish.json" if source_name is None else f"{source_name}{SIDECAR_SUFFIX}"
    return source_dir / "_derived" / name


def validate_sidecar(sidecar: Mapping[str, Any]) -> None:
    """Raise ``ValueError`` when a publication record violates v1 invariants."""

    if sidecar.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported sidecar schema_version")
    try:
        status = PublishStatus(sidecar["status"])
    except (KeyError, ValueError) as exc:
        raise ValueError("invalid publication status") from exc
    if sidecar.get("publishable") is not status.publishable:
        raise ValueError("publishable does not match status")
    if sidecar.get("aggregation_allowed") is not False:
        raise ValueError("aggregation_allowed must be false in v1")
    protocol = sidecar.get("protocol")
    if not isinstance(protocol, Mapping):
        raise ValueError("protocol is required")
    expected_fp = protocol_fingerprint(protocol.get("recorded") or {}, protocol.get("inferred") or {})
    if protocol.get("fingerprint") != expected_fp:
        raise ValueError("protocol fingerprint mismatch")
    unknown = set(protocol.get("unknown") or [])
    if status.publishable and unknown & COMPARISON_CRITICAL_UNKNOWN:
        raise ValueError("publishable sidecar has comparison-critical unknown provenance")
    if sidecar.get("benchmark_id") == "KRETA" and status.publishable:
        recorded = protocol.get("recorded") or {}
        if (
            recorded.get("answer_parser_version") != KRETA_ANSWER_PARSER_VERSION
            or recorded.get("answer_parser_hash") != KRETA_ANSWER_PARSER_HASH
        ):
            raise ValueError("KRETA sidecar does not bind the current answer parser")
    counts = sidecar.get("counts") or {}
    attempted = counts.get("attempted")
    measured = counts.get("measured")
    errored = counts.get("errored")
    unresolved = counts.get("unresolved")
    if all(isinstance(x, int) for x in (attempted, measured, errored, unresolved)):
        if attempted != measured + errored + unresolved:
            raise ValueError("attempted count invariant failed")
    if status.publishable and (errored or unresolved):
        raise ValueError("publishable sidecar contains failed records")


def sidecar_json(sidecar: Mapping[str, Any]) -> str:
    validate_sidecar(sidecar)
    return json.dumps(sidecar, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
