"""Publication sidecar schema, canonical serialization, and invariants."""

from __future__ import annotations

import hashlib
import json
import math
import re
from copy import deepcopy
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping


SCHEMA_VERSION = 1
# Bumped whenever the *meaning* of a fingerprint changes, so a sidecar written
# by older code is recognizable as stale rather than as a damaged artifact.
# 2: hash the effective protocol (recorded merged with inferred values, no-op
#    serving constraints dropped) instead of the raw recorded/inferred blocks.
FINGERPRINT_VERSION = 2
STALE_FINGERPRINT_PREFIX = "protocol fingerprint version"
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
    # External-judge provenance.  Recording *more* about a judge must not fork
    # the cohort away from every run made before the field existed — the same
    # rule that already applies to dataset provenance.  Judge identity still
    # splits a cohort through `judge_model` and `judge_prompt_version`, and a
    # template that changed under a stable version string is caught by the
    # cohort drift check rather than by silently separating the runs.
    "judge_base_url",
    "judge_served_identity",
    "judge_prompt_template_sha256",
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


KRETA_ANSWER_PARSER_HASH = sha256_bytes(
    canonical_json(KRETA_ANSWER_PARSER_SPEC).encode("utf-8")
)

MODEL_IDENTITY_CONFIG = Path("configs/model_identity.json")
UNMAPPED_MODEL_WARNING_PREFIX = "모델 정체성 미매핑:"
ACCURACY_BENCHMARK_IDS = {"KRETA", "K-MMBench", "K-DTCBench", "MTVQA-KR"}


def _model_identity_markers(name: str) -> set[str]:
    normalized = name.lower()
    markers = set(re.findall(r"\d+(?:\.\d+)?b", normalized))
    markers.update(re.findall(
        r"(?:fp|int|uint)\d+|(?:\d+bit)|nf4|bnb|gptq|awq|gguf|q\d+(?:_[a-z0-9]+)*",
        normalized,
    ))
    return markers


def load_model_identity_map(base: Path) -> dict[str, str]:
    """Load the explicit serving-name to canonical-model mapping.

    A missing config is treated as an empty mapping so publication remains
    fail-safe: every serving name stays distinct and is visibly marked as
    unmapped.  Invalid mappings are rejected instead of guessed.
    """

    path = Path(base) / MODEL_IDENTITY_CONFIG
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or any(
        not isinstance(name, str) or not name or not isinstance(canonical, str) or not canonical
        for name, canonical in value.items()
    ):
        raise ValueError(f"invalid model identity mapping: {path}")
    for serving_name, canonical_id in value.items():
        serving_markers = _model_identity_markers(serving_name)
        canonical_markers = _model_identity_markers(canonical_id)
        if serving_markers != canonical_markers:
            raise ValueError(
                "unsafe model identity mapping changes size/quantization markers: "
                f"{serving_name!r} -> {canonical_id!r} "
                f"({sorted(serving_markers)} != {sorted(canonical_markers)})"
            )
    return dict(value)


def resolve_model_identity(serving_name: Any, mapping: Mapping[str, str]) -> dict[str, Any]:
    """Resolve only an explicit alias; never infer model equivalence."""

    name = str(serving_name or "")
    mapped = name in mapping
    return {
        "canonical_id": mapping[name] if mapped else name,
        "serving_name": name,
        "mapped": mapped,
    }


def apply_model_identity(
    sidecar: Mapping[str, Any],
    mapping: Mapping[str, str],
) -> tuple[dict[str, Any], bool]:
    """Return a sidecar carrying current identity metadata and warning state."""

    updated = deepcopy(dict(sidecar))
    identity = resolve_model_identity(updated.get("model"), mapping)
    changed = updated.get("model_identity") != identity
    updated["model_identity"] = identity
    warnings = [
        warning
        for warning in list(updated.get("warnings") or [])
        if not str(warning).startswith(UNMAPPED_MODEL_WARNING_PREFIX)
    ]
    if not identity["mapped"]:
        warnings.append(
            f"{UNMAPPED_MODEL_WARNING_PREFIX} {identity['serving_name']} — 자기 이름을 canonical id로 사용"
        )
    if warnings != list(updated.get("warnings") or []):
        changed = True
    updated["warnings"] = warnings
    return updated, changed


def canonical_model_id(sidecar: Mapping[str, Any]) -> str:
    identity = sidecar.get("model_identity")
    if isinstance(identity, Mapping) and isinstance(identity.get("canonical_id"), str):
        return identity["canonical_id"]
    return str(sidecar.get("model"))


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


def _is_noop_serving_constraints(value: Any) -> bool:
    """True when the snapshot means "no SERVING_* constraint was applied".

    ``shared/serving/constraints.py`` is a documented no-op when its env vars are
    unset, so a run that records an all-empty snapshot sent byte-identical
    requests to a run made before the field existed.  Treating the two as
    different protocols would fork every cohort at the moment the field landed.
    ``force_skip_special_tokens=False`` is an applied constraint, not an absence,
    so only ``None`` counts as unset.
    """

    if not isinstance(value, Mapping):
        return value is None
    if value.get("unsupported_sampling_params") or value.get("removed_parameters"):
        return False
    if any(
        value.get(key) is not None
        for key in ("max_output_tokens", "force_skip_special_tokens", "skip_special_tokens")
    ):
        return False
    # A constraint this code does not know about must not be read as absence.
    known = {
        "unsupported_sampling_params",
        "removed_parameters",
        "max_output_tokens",
        "force_skip_special_tokens",
        "skip_special_tokens",
    }
    return not any(
        key not in known and value.get(key) not in (None, [], {}, "")
        for key in value
    )


def effective_protocol(recorded: Mapping[str, Any], inferred: Mapping[str, Any]) -> dict[str, Any]:
    """Protocol facts keyed by value, not by how the value was learned.

    ``inferred`` entries carry ``{"value", "basis"}``; only the value defines the
    protocol.  A run that records ``max_tokens=32`` and a legacy run whose 32 was
    restored from the runner convention issued the same requests, so they share a
    cohort.  The recorded/inferred split stays in the sidecar for reporting —
    honesty about provenance is a reporting duty, not an identity.
    """

    effective: dict[str, Any] = {}
    # Keys a source declared but which carry no protocol meaning.  They must be
    # remembered: a key dropped as a no-op is still "seen", so a later source
    # claiming an applied value for it is a contradiction, not a first sighting.
    dropped_as_noop: set[str] = set()
    for source in (recorded, inferred):
        is_inferred = source is inferred
        for key, raw in source.items():
            if key in FINGERPRINT_INFORMATIONAL_RECORDED:
                continue
            value = raw.get("value") if is_inferred and isinstance(raw, Mapping) else raw
            noop = key == "serving_constraints" and _is_noop_serving_constraints(value)
            if key in effective or key in dropped_as_noop:
                # The two sources agree only when both are no-ops or both hold
                # the same value.  Folding a disagreement away silently would
                # publish a protocol identity contradicting its own provenance.
                previous = effective.get(key)
                if (key in dropped_as_noop and not noop) or (
                    key in effective and previous != value
                ):
                    raise ValueError(
                        f"protocol records and infers different {key}: "
                        f"{previous!r} vs {value!r}"
                    )
                continue
            if noop:
                dropped_as_noop.add(key)
                continue
            effective[key] = value
    return effective


def protocol_fingerprint(recorded: Mapping[str, Any], inferred: Mapping[str, Any]) -> str:
    """Hash protocol facts only; model and run identifiers are intentionally absent."""

    return sha256_bytes(
        canonical_json({"protocol": effective_protocol(recorded, inferred)}).encode("utf-8")
    )


def make_protocol(
    recorded: Mapping[str, Any],
    inferred: Mapping[str, Any],
    unknown: list[str] | tuple[str, ...],
) -> dict[str, Any]:
    unknown_sorted = sorted(set(unknown))
    return {
        "fingerprint": protocol_fingerprint(recorded, inferred),
        "fingerprint_version": FINGERPRINT_VERSION,
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
    if status is PublishStatus.UNSCORED and not (
        sidecar.get("benchmark_id") == "KOFFVQA"
        and sidecar.get("variant") == "generation"
    ):
        raise ValueError("UNSCORED is only valid for KOFFVQA / generation")
    if sidecar.get("aggregation_allowed") is not False:
        raise ValueError("aggregation_allowed must be false in v1")
    identity = sidecar.get("model_identity")
    if identity is not None:
        if not isinstance(identity, Mapping):
            raise ValueError("model_identity must be an object")
        if not isinstance(identity.get("canonical_id"), str) or not identity.get("canonical_id"):
            raise ValueError("model_identity.canonical_id is required")
        if identity.get("serving_name") != str(sidecar.get("model")):
            raise ValueError("model_identity.serving_name must preserve model")
        if not isinstance(identity.get("mapped"), bool):
            raise ValueError("model_identity.mapped must be boolean")
    protocol = sidecar.get("protocol")
    if not isinstance(protocol, Mapping):
        raise ValueError("protocol is required")
    # Check the algorithm before the value.  A sidecar written by older code has
    # a fingerprint this code would never produce, and reporting that as a
    # mismatch reads as artifact corruption when it only needs re-deriving.
    stored_version = protocol.get("fingerprint_version")
    if stored_version != FINGERPRINT_VERSION:
        raise ValueError(
            f"{STALE_FINGERPRINT_PREFIX} {stored_version!r} != {FINGERPRINT_VERSION} "
            "— re-derive required (원본 손상 아님)"
        )
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
    if status.publishable and sidecar.get("benchmark_id") in ACCURACY_BENCHMARK_IDS:
        axes = ((sidecar.get("metrics") or {}).get("axes") or [])
        overall = next(
            (axis for axis in axes if isinstance(axis, Mapping) and axis.get("name") == "overall"),
            None,
        )
        if not isinstance(overall, Mapping) or overall.get("unit") != "fraction":
            raise ValueError("publishable accuracy sidecar requires overall fraction axis")
        numerator, denominator, value = (
            overall.get("numerator"), overall.get("denominator"), overall.get("value")
        )
        if (
            isinstance(numerator, bool) or not isinstance(numerator, int)
            or isinstance(denominator, bool) or not isinstance(denominator, int)
            or denominator <= 0 or not 0 <= numerator <= denominator
            or isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isclose(float(value), numerator / denominator, rel_tol=1e-12, abs_tol=1e-12)
        ):
            raise ValueError("invalid publishable overall fraction axis")
    counts = sidecar.get("counts") or {}
    attempted = counts.get("attempted")
    measured = counts.get("measured")
    errored = counts.get("errored")
    unresolved = counts.get("unresolved")
    correct_measured = counts.get("correct_measured")
    if status.publishable:
        required_counts = (attempted, measured, errored, unresolved, correct_measured)
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in required_counts):
            raise ValueError("publishable counts must contain nonnegative integer attempted/measured/errored/unresolved/correct_measured")
        if not correct_measured <= measured <= attempted:
            raise ValueError("publishable count ordering invariant failed")
    if all(isinstance(x, int) and not isinstance(x, bool) for x in (attempted, measured, errored, unresolved)):
        if attempted != measured + errored + unresolved:
            raise ValueError("attempted count invariant failed")
    if status.publishable and (errored or unresolved):
        raise ValueError("publishable sidecar contains failed records")


def sidecar_json(sidecar: Mapping[str, Any]) -> str:
    validate_sidecar(sidecar)
    return json.dumps(sidecar, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
