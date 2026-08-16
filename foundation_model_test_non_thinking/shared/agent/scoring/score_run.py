"""CLI for deterministic Ko-AgentBench agent scoring."""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

if __package__:
    from .aggregate import ALL_LEVELS, build_summary_from_loaded, safe_model_name
    from .level_spec import LEVEL_SPECS, LEVEL_SPECS_V3
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from aggregate import ALL_LEVELS, build_summary_from_loaded, safe_model_name
    from level_spec import LEVEL_SPECS, LEVEL_SPECS_V3


PREFIX = "[agent-scoring]"
DETERMINISTIC_METRICS = {
    spec.name
    for level_specs in (LEVEL_SPECS, LEVEL_SPECS_V3)
    for specs in level_specs.values()
    for spec in specs
}


def _fmt(value: Optional[float]) -> str:
    return "null" if value is None else f"{value:.3f}"


def _metric_token(name: str, entry: Dict[str, Any]) -> str:
    token = f"{name}={_fmt(entry.get('score'))}/{entry.get('status')}"
    n_scored = entry.get("n_scored")
    n_tasks = entry.get("n_tasks")
    if isinstance(n_scored, int) and isinstance(n_tasks, int) and n_scored < n_tasks:
        token += f"(applicable={n_scored}/{n_tasks})"
    return token


def _cache_token(entry: Dict[str, Any]) -> str:
    names = (
        "exact",
        "presentation_sibling",
        "semantic_mismatch",
        "query_absent",
        "signature_mismatch",
        "tool_absent",
        "unclassified",
    )
    counts = entry.get("counts") or {}
    miss_counts = entry.get("miss_counts") or {}
    compact = "/".join(str(counts.get(name, 0)) for name in names)
    miss_compact = "/".join(str(miss_counts.get(name, 0)) for name in names)
    return (
        f"cache_miss={entry.get('cache_misses', 0)}/{entry.get('total_calls', 0)}"
        f"({_fmt(entry.get('miss_rate'))}) buckets=e/ps/sm/qa/sig/ta/u:{compact}"
        f" miss_buckets=e/ps/sm/qa/sig/ta/u:{miss_compact}"
    )


def _result_dir_from_args(args) -> Path:
    if args.results_dir:
        return Path(args.results_dir).resolve()
    base = os.environ.get("MODEL_TEST_BASE")
    if not base:
        raise RuntimeError("--results-dir or MODEL_TEST_BASE is required")
    if not args.model or not args.timestamp:
        raise RuntimeError("--model and --timestamp are required without --results-dir")
    return (
        Path(base).resolve()
        / "results"
        / safe_model_name(args.model)
        / args.timestamp
        / "language"
        / args.track
    )


def _load_level(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_summary(results_dir: Path) -> Dict[str, Any]:
    if not results_dir.is_dir():
        raise RuntimeError(f"results dir not found: {results_dir}")

    loaded = {}
    for level in ALL_LEVELS:
        path = results_dir / f"{level}.json"
        if path.is_file():
            loaded[level] = _load_level(path)

    return build_summary_from_loaded(loaded, results_dir)


def print_table(summary: Dict[str, Any], skipped_count: int) -> None:
    print(f"{PREFIX} model={summary['model']} track={summary['track']}")
    cache_by_level = (
        (summary.get("cache_miss_diagnostics") or {}).get("by_level") or {}
    )
    for level in ALL_LEVELS:
        result = summary["by_level"].get(level)
        if not result:
            continue
        metrics = " ".join(
            _metric_token(name, entry)
            for name, entry in result["metrics"].items()
            if entry.get("in_score") or name in DETERMINISTIC_METRICS
        )
        unscorable = ""
        if result.get("score") is None and result.get("unscorable_reason"):
            unscorable = f" unscorable={result['unscorable_reason']}"
        declared_metrics = sum(spec.in_score for spec in LEVEL_SPECS[level])
        applied = result.get("applied_metrics")
        applied_token = ""
        if isinstance(applied, int) and applied < declared_metrics:
            applied_token = f" applied_metrics={applied}/{declared_metrics}"
        print(
            f"{PREFIX} {level} total={result['total']} "
            f"score={_fmt(result.get('score'))}{unscorable}{applied_token} {metrics}"
            + (
                f" {_cache_token(cache_by_level[level])}"
                if isinstance(cache_by_level.get(level), dict)
                else ""
            )
        )
    scored_levels = summary.get(
        "scored_levels",
        sum(
            result.get("score") is not None
            for result in summary.get("by_level", {}).values()
        ),
    )
    required_levels = summary.get("required_levels", len(ALL_LEVELS) - 1)
    print(
        f"{PREFIX} agent_score={_fmt(summary.get('agent_score'))} "
        f"status={summary.get('agent_score_status', 'unknown')} "
        f"scored_levels={scored_levels}/{required_levels}"
    )
    v3 = summary.get("scoring_v3")
    if isinstance(v3, dict):
        l6 = (v3.get("by_level") or {}).get("L6")
        if isinstance(l6, dict):
            metrics = " ".join(
                _metric_token(name, entry)
                for name, entry in l6.get("metrics", {}).items()
                if entry.get("in_score") or name in DETERMINISTIC_METRICS
            )
            print(
                f"{PREFIX} v3 L6 total={l6['total']} "
                f"score={_fmt(l6.get('score'))} {metrics}"
            )
        print(
            f"{PREFIX} v3 agent_score={_fmt(v3.get('agent_score'))} "
            f"status={v3.get('agent_score_status', 'unknown')} "
            f"scored_levels={v3.get('scored_levels')}/{v3.get('required_levels')}"
        )
    cache_overall = (
        (summary.get("cache_miss_diagnostics") or {}).get("overall") or {}
    )
    if isinstance(cache_overall, dict):
        print(f"{PREFIX} cache overall {_cache_token(cache_overall)}")
    print(f"{PREFIX} skipped_missing_levels={skipped_count}")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", help="Path to language/<track> containing L*.json")
    parser.add_argument("--model", help="Model name used to build results path")
    parser.add_argument("--timestamp", help="Evaluation timestamp used to build results path")
    parser.add_argument("--track", default="agent", help="Track folder under language/")
    parser.add_argument("--dry-run", action="store_true", help="Do not write summary.json")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        results_dir = _result_dir_from_args(args)
        summary = build_summary(results_dir)
        skipped = len(summary["levels_missing"])
        print_table(summary, skipped)
        if not args.dry_run:
            out = results_dir / "summary.json"
            with out.open("w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)
            print(f"{PREFIX} wrote {out}")
        return 0
    except Exception as exc:
        print(f"{PREFIX} error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
