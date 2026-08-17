"""CLI for deterministic Ko-AgentBench agent scoring."""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

if __package__:
    from .aggregate import (
        ALL_LEVELS,
        L4_FIXTURE_COVERAGE_NOTICE,
        SCORABLE_LEVELS,
        V4_HEADLINE_LEVELS,
        build_summary_from_loaded,
        safe_model_name,
    )
    from . import SCORING_VERSION, SCORING_VERSION_V3, SCORING_VERSION_V4
    from .context import load_metrics_module
    from .level_spec import LEVEL_SPECS, LEVEL_SPECS_V3
    from .validate_run import validate_summary
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from aggregate import (
        ALL_LEVELS,
        L4_FIXTURE_COVERAGE_NOTICE,
        SCORABLE_LEVELS,
        V4_HEADLINE_LEVELS,
        build_summary_from_loaded,
        safe_model_name,
    )
    from __init__ import SCORING_VERSION, SCORING_VERSION_V3, SCORING_VERSION_V4
    from context import load_metrics_module
    from level_spec import LEVEL_SPECS, LEVEL_SPECS_V3
    from validate_run import validate_summary


PREFIX = "[agent-scoring]"
MAX_DRIFT_LINES = 40
EXIT_CODE_HELP = """exit codes:
  0  summary produced and publishable, or --check found no drift
  1  scoring completed but the summary is unusable, or --check found drift
  2  invocation, configuration, input-reading, or internal error"""
DETERMINISTIC_METRICS = {
    spec.name
    for level_specs in (LEVEL_SPECS, LEVEL_SPECS_V3)
    for specs in level_specs.values()
    for spec in specs
}


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


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


def _denominator_token(levels) -> str:
    return "(" + ",".join(f'"{level}"' for level in levels) + ")"


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
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("top-level JSON value must be an object")
    return data


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
        f"{PREFIX} version={SCORING_VERSION} "
        f"denominator={_denominator_token(SCORABLE_LEVELS)} "
        f"agent_score={_fmt(summary.get('agent_score'))} "
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
            f"{PREFIX} version={SCORING_VERSION_V3} "
            f"denominator={_denominator_token(SCORABLE_LEVELS)} "
            f"agent_score={_fmt(v3.get('agent_score'))} "
            f"status={v3.get('agent_score_status', 'unknown')} "
            f"scored_levels={v3.get('scored_levels')}/{v3.get('required_levels')}"
        )
    v4 = summary.get("scoring_v4")
    if isinstance(v4, dict):
        print(
            f"{PREFIX} version={SCORING_VERSION_V4} "
            f"denominator={_denominator_token(V4_HEADLINE_LEVELS)} "
            f"agent_score={_fmt(v4.get('agent_score'))} "
            f"status={v4.get('agent_score_status', 'unknown')} "
            f"scored_levels={v4.get('scored_levels')}/{v4.get('required_levels')}"
        )

        v3_by_level = (v3 or {}).get("by_level") or {}
        v4_by_level = v4.get("by_level") or {}
        for level in ALL_LEVELS:
            v2_result = (summary.get("by_level") or {}).get(level)
            v3_result = v3_by_level.get(level)
            v4_result = v4_by_level.get(level)
            if not any(isinstance(item, dict) for item in (v2_result, v3_result, v4_result)):
                continue
            cache = cache_by_level.get(level)
            cache_token = (
                f" {_cache_token(cache)}"
                if level == "L4" and isinstance(cache, dict)
                else ""
            )
            print(
                f"{PREFIX} matrix {level} "
                f"{SCORING_VERSION}={_fmt((v2_result or {}).get('score'))} "
                f"{SCORING_VERSION_V3}={_fmt((v3_result or {}).get('score'))} "
                f"{SCORING_VERSION_V4}={_fmt((v4_result or {}).get('score'))}"
                f"{cache_token}"
            )
        print(f"{PREFIX} NOTE {L4_FIXTURE_COVERAGE_NOTICE}")
    cache_overall = (
        (summary.get("cache_miss_diagnostics") or {}).get("overall") or {}
    )
    if isinstance(cache_overall, dict):
        print(f"{PREFIX} cache overall {_cache_token(cache_overall)}")
    print(f"{PREFIX} skipped_missing_levels={skipped_count}")


def _write_json_atomic(path: Path, payload: Dict[str, Any]) -> None:
    fd, temp_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def _json_leaf_count(value: Any) -> int:
    if isinstance(value, dict):
        return sum((_json_leaf_count(item) for item in value.values()), 0) or 1
    if isinstance(value, list):
        return sum((_json_leaf_count(item) for item in value), 0) or 1
    return 1


def _absent_difference(marker: str, path: str, value: Any, location: str) -> str:
    if isinstance(value, (dict, list)):
        count = _json_leaf_count(value)
        noun = "leaf" if count == 1 else "leaves"
        return f"{marker} {path} ({count} {noun} absent in {location})"
    return f"{marker} {path} (absent in {location})"


def _render_json_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _json_differences(stored: Any, computed: Any, path: str = ".") -> List[str]:
    if isinstance(stored, dict) and isinstance(computed, dict):
        differences = []
        for key in sorted(stored.keys() | computed.keys()):
            child_path = f"{path}{key}" if path == "." else f"{path}.{key}"
            if key not in stored:
                differences.append(
                    _absent_difference("DRIFT+", child_path, computed[key], "stored")
                )
            elif key not in computed:
                differences.append(
                    _absent_difference("DRIFT-", child_path, stored[key], "computed")
                )
            else:
                differences.extend(
                    _json_differences(stored[key], computed[key], child_path)
                )
        return differences

    if isinstance(stored, list) and isinstance(computed, list):
        differences = []
        common = min(len(stored), len(computed))
        for index in range(common):
            differences.extend(
                _json_differences(stored[index], computed[index], f"{path}[{index}]")
            )
        for index in range(common, len(stored)):
            differences.append(
                _absent_difference(
                    "DRIFT-", f"{path}[{index}]", stored[index], "computed"
                )
            )
        for index in range(common, len(computed)):
            differences.append(
                _absent_difference(
                    "DRIFT+", f"{path}[{index}]", computed[index], "stored"
                )
            )
        return differences

    # JSON에서 bool은 숫자와 별도 타입이므로 True와 1을 같다고 보지 않는다.
    same_value = stored == computed
    if isinstance(stored, bool) != isinstance(computed, bool):
        same_value = False
    if same_value:
        return []
    return [
        f"DRIFT {path} stored={_render_json_value(stored)} "
        f"computed={_render_json_value(computed)}"
    ]


def _print_differences(differences: List[str]) -> None:
    for difference in differences[:MAX_DRIFT_LINES]:
        print(f"{PREFIX} {difference}")
    suppressed = len(differences) - MAX_DRIFT_LINES
    if suppressed > 0:
        print(f"{PREFIX} DRIFT ... {suppressed} additional differences suppressed")


def parse_args(argv=None):
    parser = _ArgumentParser(
        description=__doc__,
        epilog=EXIT_CODE_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--results-dir", help="Path to language/<track> containing L*.json")
    parser.add_argument("--model", help="Model name used to build results path")
    parser.add_argument("--timestamp", help="Evaluation timestamp used to build results path")
    parser.add_argument("--track", default="agent", help="Track folder under language/")
    output_mode = parser.add_mutually_exclusive_group()
    output_mode.add_argument("--dry-run", action="store_true", help="Do not write summary.json")
    output_mode.add_argument(
        "--check",
        action="store_true",
        help="Compare with summary.json without writing anything",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    try:
        args = parse_args(argv)
        results_dir = _result_dir_from_args(args)
        stored_summary = None
        if args.check:
            summary_path = results_dir / "summary.json"
            if not summary_path.is_file():
                raise RuntimeError(f"summary.json not found: {summary_path}")
            with summary_path.open("r", encoding="utf-8") as handle:
                stored_summary = json.load(handle)
        # 벤치 패키지는 실행 전체의 전제다. 태스크별 예외 처리 밖에서 한 번만
        # 확인해 구성 실패가 메트릭 오류로 세탁되지 않게 한다.
        load_metrics_module()
        summary = build_summary(results_dir)
        skipped = len(summary["levels_missing"])
        print_table(summary, skipped)
        failures, warnings = validate_summary(summary, results_dir)
        for warning in warnings:
            print(f"{PREFIX} WARN {warning}")
        if failures:
            for failure in failures:
                print(f"{PREFIX} FAIL {failure}")
        if args.check:
            differences = _json_differences(stored_summary, summary)
            if differences:
                _print_differences(differences)
                return 1
            print(f"{PREFIX} CHECK summary.json matches computed summary")
            return 0
        if failures:
            if not args.dry_run:
                invalid_out = results_dir / "summary.invalid.json"
                _write_json_atomic(invalid_out, summary)
                print(f"{PREFIX} wrote {invalid_out}")
            return 1
        if not args.dry_run:
            out = results_dir / "summary.json"
            invalid_out = results_dir / "summary.invalid.json"
            invalid_out.unlink(missing_ok=True)
            _write_json_atomic(out, summary)
            print(f"{PREFIX} wrote {out}")
        return 0
    except Exception as exc:
        print(f"{PREFIX} error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
