#!/usr/bin/env python3
"""FunctionChat raw artifacts를 deterministic ``summary.json``으로 채점한다."""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Tuple

if __package__:
    from .exact_match import CALL, exact_match
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from exact_match import CALL, exact_match


SCORING_VERSION = "functionchat_exact_v1"
RAW_DATASETS = ("singlecall", "call_decision")
INTEGRITY_FIELDS = (
    "model",
    "request_timeout",
    "task_timeout",
    "max_retries",
    "max_tokens",
    "native_tool_calling",
    "sdk_max_retries",
    "openai_sdk_version",
)


def safe_model_name(model: str) -> str:
    return model.replace("/", "_").replace("-", "_").replace(":", "_")


def score_items(items: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    measured = passed = failed = 0
    not_measured: Dict[str, int] = {}
    for item in items:
        output_type = item.get("type_of_output")
        if output_type != CALL:
            key = str(output_type or "unknown")
            not_measured[key] = not_measured.get(key, 0) + 1
            continue
        measured += 1
        if exact_match(dict(item), item.get("model_output")):
            passed += 1
        else:
            failed += 1
    return {
        "accuracy": passed / measured if measured else None,
        "measured": measured,
        "passed": passed,
        "failed": failed,
        "not_measured": dict(sorted(not_measured.items())),
    }


def _identity(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _shared_integrity(raw_by_dataset: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any]:
    metadata = {
        name: dict(data.get("metadata") or {}) for name, data in raw_by_dataset.items()
    }
    shared: Dict[str, Any] = {}
    for field in INTEGRITY_FIELDS:
        values = {name: meta.get(field) for name, meta in metadata.items()}
        if any(field not in meta for meta in metadata.values()):
            raise ValueError(f"raw metadata.{field} missing: {values}")
        if len({_identity(value) for value in values.values()}) != 1:
            raise ValueError(f"raw metadata.{field} disagrees across datasets: {values}")
        shared[field] = next(iter(values.values()))
    return shared


def build_summary(
    raw_by_dataset: Mapping[str, Mapping[str, Any]],
    coverage: Mapping[str, Any],
    track: str,
) -> Dict[str, Any]:
    missing = [name for name in RAW_DATASETS if name not in raw_by_dataset]
    if missing:
        raise ValueError(f"raw dataset artifacts missing: {missing}")

    integrity = _shared_integrity(raw_by_dataset)
    by_dataset = {
        name: score_items(raw_by_dataset[name].get("results") or [])
        for name in RAW_DATASETS
    }
    measured = sum(entry["measured"] for entry in by_dataset.values())
    passed = sum(entry["passed"] for entry in by_dataset.values())
    failed = sum(entry["failed"] for entry in by_dataset.values())

    declared_not_measured = coverage.get("not_measured") or {}
    decision_declared = dict(declared_not_measured.get("call_decision") or {})
    decision_observed = by_dataset["call_decision"]["not_measured"]
    if decision_declared != decision_observed:
        raise ValueError(
            "CallDecision not-measured counts disagree: "
            f"coverage={decision_declared}, raw={decision_observed}"
        )
    dialog_declared = dict(declared_not_measured.get("dialog") or {})
    not_measured_total = sum(decision_declared.values()) + sum(dialog_declared.values())

    return {
        "benchmark": "kakao/FunctionChat-Bench (call exact match)",
        "model": integrity["model"],
        "track": track,
        "scoring_version": SCORING_VERSION,
        "native_tool_calling": integrity["native_tool_calling"],
        "harness_integrity": integrity,
        "overall": {
            "accuracy": passed / measured if measured else None,
            "measured": measured,
            "passed": passed,
            "failed": failed,
        },
        "by_dataset": by_dataset,
        "not_measured": {
            "score": None,
            "status": "judge_missing",
            "in_score": False,
            "reason": "These output types require an LLM judge and are outside this exact-match track.",
            "total_items": not_measured_total,
            "by_dataset": {
                "call_decision": decision_declared,
                "dialog": dialog_declared,
            },
        },
        "coverage": dict(coverage.get("datasets") or {}),
        "source": dict(coverage.get("source") or {}),
    }


def _load(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {path}")
    return data


def _write_atomic(path: Path, data: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def _results_dir(args: argparse.Namespace) -> Path:
    if args.results_dir:
        return args.results_dir.resolve()
    base = Path(os.environ.get("MODEL_TEST_BASE") or Path(__file__).resolve().parents[3])
    timestamp = args.timestamp or os.environ.get("EVAL_TIMESTAMP")
    if not args.model or not timestamp:
        raise ValueError("--model and --timestamp (or EVAL_TIMESTAMP) are required")
    return base / "results" / safe_model_name(args.model) / timestamp / "language" / args.track


def parse_args(argv: List[str] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model")
    parser.add_argument("--timestamp")
    parser.add_argument("--track", default="functionchat")
    parser.add_argument("--results-dir", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: List[str] = None) -> int:
    try:
        args = parse_args(argv)
        results_dir = _results_dir(args)
        raw = {name: _load(results_dir / f"{name}.json") for name in RAW_DATASETS}
        coverage = _load(results_dir / "coverage.json")
        summary = build_summary(raw, coverage, args.track)
        for name, entry in summary["by_dataset"].items():
            print(
                f"[functionchat-scoring] {name}: {entry['passed']}/{entry['measured']} "
                f"accuracy={entry['accuracy']:.6f}"
            )
        overall = summary["overall"]
        print(
            f"[functionchat-scoring] overall: {overall['passed']}/{overall['measured']} "
            f"accuracy={overall['accuracy']:.6f}; "
            f"not_measured={summary['not_measured']['total_items']}"
        )
        if not args.dry_run:
            _write_atomic(results_dir / "summary.json", summary)
            print(f"[functionchat-scoring] wrote {results_dir / 'summary.json'}")
        return 0
    except Exception as exc:
        print(f"[functionchat-scoring] ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
