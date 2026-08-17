"""Validate one agent-track result directory.

The CLI reads only ``summary.json`` and direct ``L1.json`` ... ``L7.json``
children of the selected agent results directory. It never inspects other tracks.

Exit codes:
    0  Results are valid (warnings are allowed).
    1  Results are invalid because validation errors were found.
    2  Invocation, configuration, input-reading, or unexpected internal error.
"""

import argparse
import json
import math
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

if __package__:
    from . import SCORING_VERSION, SCORING_VERSION_V3, SCORING_VERSION_V4
    from .aggregate import (
        ALL_LEVELS,
        SCORABLE_LEVELS,
        V4_EXCLUDED_LEVELS,
        V4_HEADLINE_LEVELS,
        safe_model_name,
    )
    from .level_spec import JUDGE_METRICS, LEVEL_SPECS, LEVEL_SPECS_V3
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from __init__ import SCORING_VERSION, SCORING_VERSION_V3, SCORING_VERSION_V4
    from aggregate import (
        ALL_LEVELS,
        SCORABLE_LEVELS,
        V4_EXCLUDED_LEVELS,
        V4_HEADLINE_LEVELS,
        safe_model_name,
    )
    from level_spec import JUDGE_METRICS, LEVEL_SPECS, LEVEL_SPECS_V3


PREFIX = "[agent-validate]"
NO_SCORE_STATUSES = {"not_applicable", "error", "contract_error", "judge_missing"}
CACHE_MISS_WARNING_THRESHOLD = 0.20
EXIT_CODE_HELP = """exit codes:
  0  results valid (warnings allowed)
  1  results invalid -- validation errors found
  2  invocation, configuration, input-reading, or internal error"""


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_finite_score(value: Any) -> bool:
    return _is_number(value) and math.isfinite(value) and 0.0 <= value <= 1.0


def _results_dir_from_args(args) -> Path:
    if args.results_dir is not None:
        if not args.results_dir:
            raise RuntimeError("--results-dir must not be empty")
        if args.model is not None or args.timestamp is not None or args.track is not None:
            raise RuntimeError(
                "--results-dir cannot be combined with --model, --timestamp, or --track"
            )
        return Path(args.results_dir).resolve()
    base = os.environ.get("MODEL_TEST_BASE")
    if not base:
        raise RuntimeError("MODEL_TEST_BASE is required without --results-dir")
    if not args.model or not args.timestamp:
        raise RuntimeError("--model and --timestamp are required without --results-dir")
    return (
        Path(base).resolve()
        / "results"
        / safe_model_name(args.model)
        / args.timestamp
        / "language"
        / (args.track or "agent")
    )


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("top-level JSON value must be an object")
    return data


def _preflight_results_dir(results_dir: Path) -> None:
    if not results_dir.exists():
        raise RuntimeError(f"results directory does not exist: {results_dir}")
    if not results_dir.is_dir():
        raise RuntimeError(f"results path is not a directory: {results_dir}")

    summary_path = results_dir / "summary.json"
    if not summary_path.exists():
        return

    direct_json = [summary_path]
    direct_json.extend(results_dir / f"{level}.json" for level in ALL_LEVELS)
    for path in direct_json:
        if path.exists():
            try:
                _load_json(path)
            except Exception as exc:
                raise RuntimeError(
                    f"{path.name} could not be read or parsed: "
                    f"{type(exc).__name__}: {exc}"
                ) from exc


def _check_score(
    value: Any, label: str, failures: List[str], allow_none: bool = True
) -> None:
    if value is None and allow_none:
        return
    if not _is_number(value):
        failures.append(f"{label} must be a number or null")
    elif not math.isfinite(value) or not 0.0 <= value <= 1.0:
        failures.append(f"{label} must be finite and within [0, 1], got {value!r}")


def _check_task_spread(
    level: str, metric: str, entry: Dict[str, Any], failures: List[str]
) -> None:
    if "task_spread" not in entry:
        return
    spread = entry.get("task_spread")
    if not isinstance(spread, dict):
        failures.append(f"{level}.{metric}.task_spread must be an object")
        return
    counts = []
    for name in ("n_perfect", "n_zero", "n_partial"):
        value = spread.get(name)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            failures.append(f"{level}.{metric}.task_spread.{name} must be a nonnegative integer")
            return
        counts.append(value)
    n_scored = entry.get("n_scored")
    if not isinstance(n_scored, int) or isinstance(n_scored, bool) or n_scored < 0:
        failures.append(f"{level}.{metric}.n_scored must be a nonnegative integer")
    elif sum(counts) != n_scored:
        failures.append(
            f"{level}.{metric}.task_spread counts sum to {sum(counts)}, "
            f"not n_scored={n_scored}"
        )


def _all_scored_tasks_are(result: Dict[str, Any], spread_key: str) -> bool:
    applied = [
        entry
        for entry in (result.get("metrics") or {}).values()
        if isinstance(entry, dict)
        and entry.get("in_score") is True
        and _is_finite_score(entry.get("score"))
    ]
    if not applied:
        return False
    for entry in applied:
        spread = entry.get("task_spread")
        n_scored = entry.get("n_scored")
        if (
            not isinstance(spread, dict)
            or not isinstance(n_scored, int)
            or isinstance(n_scored, bool)
            or n_scored <= 0
            or spread.get(spread_key) != n_scored
        ):
            return False
    return True


def validate_results_dir(results_dir: Path) -> Tuple[List[str], List[str]]:
    """Return ``(failures, warnings)`` for exactly one agent results directory."""

    results_dir = Path(results_dir)
    failures: List[str] = []
    warnings: List[str] = []
    summary_path = results_dir / "summary.json"
    if not summary_path.is_file():
        return ([f"summary.json not found: {summary_path}"], warnings)
    try:
        summary = _load_json(summary_path)
    except Exception as exc:
        return (
            [f"summary.json could not be parsed: {type(exc).__name__}: {exc}"],
            warnings,
        )

    if summary.get("scoring_version") != SCORING_VERSION:
        failures.append(
            f"scoring_version mismatch: expected {SCORING_VERSION!r}, "
            f"got {summary.get('scoring_version')!r}"
        )

    by_level = summary.get("by_level")
    if not isinstance(by_level, dict):
        failures.append("by_level must be an object")
        by_level = {}

    for level, result in by_level.items():
        if level not in ALL_LEVELS or not isinstance(result, dict):
            failures.append(f"invalid level entry: {level!r}")
            continue
        total = result.get("total")
        if not isinstance(total, int) or isinstance(total, bool) or total <= 0:
            failures.append(f"{level}.total must be a positive integer")
        _check_score(result.get("score"), f"{level}.score", failures)

        metrics = result.get("metrics")
        if not isinstance(metrics, dict):
            failures.append(f"{level}.metrics must be an object")
            continue
        for metric, entry in metrics.items():
            if not isinstance(entry, dict):
                failures.append(f"{level}.{metric} must be an object")
                continue
            score = entry.get("score")
            _check_score(score, f"{level}.{metric}.score", failures)
            status = entry.get("status")
            if status in NO_SCORE_STATUSES and _is_number(score):
                failures.append(f"{level}.{metric} status {status!r} must not carry a numeric score")
            if entry.get("in_score") is True and status in {"error", "partial"}:
                failures.append(f"{level}.{metric} in_score metric has unclean status {status!r}")
            _check_task_spread(level, metric, entry, failures)

        for metric in JUDGE_METRICS:
            entry = metrics.get(metric)
            if not isinstance(entry, dict):
                failures.append(f"{level}.{metric} judge metric is missing")
            elif entry.get("status") != "judge_missing" or entry.get("in_score") is not False:
                failures.append(
                    f"{level}.{metric} must remain status 'judge_missing' with in_score false"
                )

        declared = sum(spec.in_score for spec in LEVEL_SPECS[level])
        applied = result.get("applied_metrics")
        if isinstance(applied, int) and not isinstance(applied, bool) and applied < declared:
            warnings.append(f"{level} applied_metrics={applied}/{declared}")
        if result.get("score") == 1.0 and _all_scored_tasks_are(result, "n_perfect"):
            warnings.append(f"{level} is at ceiling: all scored tasks are perfect")
        if result.get("score") == 0.0 and _all_scored_tasks_are(result, "n_zero"):
            warnings.append(f"{level} is at floor: all scored tasks are zero")

    cache_by_level = (
        (summary.get("cache_miss_diagnostics") or {}).get("by_level") or {}
    )
    if isinstance(cache_by_level, dict):
        for level in SCORABLE_LEVELS:
            result = by_level.get(level)
            diagnostic = cache_by_level.get(level)
            if not isinstance(result, dict) or not _is_finite_score(result.get("score")):
                continue
            if not isinstance(diagnostic, dict):
                continue
            miss_rate = diagnostic.get("miss_rate")
            if _is_number(miss_rate) and miss_rate > CACHE_MISS_WARNING_THRESHOLD:
                warnings.append(
                    f"{level} cache miss rate {miss_rate:.1%} exceeds warning threshold "
                    f"{CACHE_MISS_WARNING_THRESHOLD:.0%} "
                    f"({diagnostic.get('cache_misses', 0)}/"
                    f"{diagnostic.get('total_calls', 0)} executed tool calls); "
                    "diagnostic only, score unchanged"
                )

    if "L7" in by_level and isinstance(by_level["L7"], dict):
        l7 = by_level["L7"]
        metrics = l7.get("metrics") or {}
        for spec in LEVEL_SPECS["L7"]:
            entry = metrics.get(spec.name)
            if not isinstance(entry, dict) or entry.get("in_score") is not False:
                failures.append(f"L7.{spec.name} must be present with in_score false")
        if l7.get("score") is not None:
            failures.append("L7 must be absent from the denominator and have a null level score")

    raw_levels: Dict[str, Dict[str, Any]] = {}
    for level in ALL_LEVELS:
        path = results_dir / f"{level}.json"
        if not path.is_file():
            continue
        try:
            raw_levels[level] = _load_json(path)
        except Exception as exc:
            failures.append(f"{level}.json could not be parsed: {type(exc).__name__}: {exc}")

    if not raw_levels:
        failures.append("no direct L1.json ... L7.json raw level files found")

    l2_select_acc = ((by_level.get("L2") or {}).get("metrics") or {}).get("SelectAcc")
    if isinstance(l2_select_acc, dict) and _is_finite_score(l2_select_acc.get("score")):
        l2_results = (raw_levels.get("L2") or {}).get("results") or []
        if isinstance(l2_results, list):
            for task in l2_results:
                if not isinstance(task, dict):
                    continue
                exposed_tools = task.get("exposed_tools")
                if isinstance(exposed_tools, list) and len(exposed_tools) == 1:
                    task_id = task.get("task_id", "unknown")
                    warnings.append(
                        f"L2 task {task_id} has only one exposed tool candidate"
                    )

    summary_native = summary.get("native_tool_calling")
    if not isinstance(summary_native, bool):
        failures.append("summary native_tool_calling must be a boolean")
    raw_native: Dict[str, bool] = {}
    for level, data in raw_levels.items():
        metadata = data.get("metadata") or {}
        if "native_tool_calling" not in metadata:
            # 필드 도입 전 raw 결과는 non-native runner만 사용했다.
            native = False
            warnings.append(
                f"{level}.json metadata.native_tool_calling missing; "
                "treating legacy run as false"
            )
        else:
            native = metadata.get("native_tool_calling")
        if not isinstance(native, bool):
            failures.append(f"{level}.json metadata.native_tool_calling must be a boolean")
        else:
            raw_native[level] = native
            if isinstance(summary_native, bool) and native != summary_native:
                failures.append(
                    f"{level}.json native_tool_calling={native} does not match summary={summary_native}"
                )
        level_score = (by_level.get(level) or {}).get("score")
        success_rate = (data.get("metadata") or {}).get("success_rate")
        if success_rate in {1.0, 100.0} and _is_finite_score(level_score) and level_score != 1.0:
            warnings.append(
                f"{level} metadata.success_rate={success_rate!r} but deterministic score={level_score:.12g}"
            )
    if len(set(raw_native.values())) > 1:
        details = ", ".join(f"{level}={value}" for level, value in sorted(raw_native.items()))
        failures.append(f"native_tool_calling disagrees across raw levels: {details}")

    headline = summary.get("agent_score")
    _check_score(headline, "agent_score", failures)
    status = summary.get("agent_score_status")
    if status not in {"complete", "incomplete"}:
        failures.append("agent_score_status must be 'complete' or 'incomplete'")
    complete = status == "complete"
    headline_is_finite = _is_finite_score(headline)
    six_scores = [
        (by_level.get(level) or {}).get("score")
        if isinstance(by_level.get(level), dict)
        else None
        for level in SCORABLE_LEVELS
    ]
    all_six_scored = all(_is_finite_score(score) for score in six_scores)
    if headline_is_finite != complete:
        failures.append("agent_score must be finite if and only if status is complete")
    if complete != all_six_scored:
        failures.append(
            "agent_score_status is complete if and only if all six scorable levels have scores"
        )
    if complete:
        if summary.get("scored_levels") != 6 or summary.get("required_levels") != 6:
            failures.append("complete run must have scored_levels == required_levels == 6")
        if headline_is_finite and all_six_scored:
            reconstructed = sum(six_scores) / len(six_scores)
            if abs(headline - reconstructed) >= 1e-9:
                failures.append(
                    f"agent_score mean invariant failed: got {headline!r}, expected {reconstructed!r}"
                )

    # V2-only summaries remain a supported historical input. When the additive
    # v3 block is present, protect its six-level mean and metric contract too.
    v3 = summary.get("scoring_v3")
    if v3 is not None:
        if not isinstance(v3, dict):
            failures.append("scoring_v3 must be an object")
        else:
            if v3.get("scoring_version") != SCORING_VERSION_V3:
                failures.append(
                    f"scoring_v3.scoring_version mismatch: expected {SCORING_VERSION_V3!r}, "
                    f"got {v3.get('scoring_version')!r}"
                )
            v3_by_level = v3.get("by_level")
            if not isinstance(v3_by_level, dict):
                failures.append("scoring_v3.by_level must be an object")
                v3_by_level = {}
            for level, result in v3_by_level.items():
                if level not in ALL_LEVELS or not isinstance(result, dict):
                    failures.append(f"scoring_v3 invalid level entry: {level!r}")
                    continue
                _check_score(
                    result.get("score"), f"scoring_v3.{level}.score", failures
                )
                metrics = result.get("metrics")
                if not isinstance(metrics, dict):
                    failures.append(f"scoring_v3.{level}.metrics must be an object")
                    continue
                expected_in_score = {
                    spec.name for spec in LEVEL_SPECS_V3[level] if spec.in_score
                }
                actual_in_score = {
                    name
                    for name, entry in metrics.items()
                    if isinstance(entry, dict) and entry.get("in_score") is True
                }
                if actual_in_score != expected_in_score:
                    failures.append(
                        f"scoring_v3.{level} in_score metric set mismatch: "
                        f"expected {sorted(expected_in_score)}, got {sorted(actual_in_score)}"
                    )
                for spec in LEVEL_SPECS_V3[level]:
                    entry = metrics.get(spec.name)
                    if not isinstance(entry, dict):
                        failures.append(
                            f"scoring_v3.{level}.{spec.name} metric is missing"
                        )
                        continue
                    if entry.get("in_score") is not spec.in_score:
                        failures.append(
                            f"scoring_v3.{level}.{spec.name}.in_score mismatch"
                        )
                    _check_score(
                        entry.get("score"),
                        f"scoring_v3.{level}.{spec.name}.score",
                        failures,
                    )
                    _check_task_spread(
                        f"scoring_v3.{level}", spec.name, entry, failures
                    )

            v3_headline = v3.get("agent_score")
            _check_score(v3_headline, "scoring_v3.agent_score", failures)
            v3_status = v3.get("agent_score_status")
            if v3_status not in {"complete", "incomplete"}:
                failures.append(
                    "scoring_v3.agent_score_status must be 'complete' or 'incomplete'"
                )
            v3_complete = v3_status == "complete"
            v3_scores = [
                (v3_by_level.get(level) or {}).get("score")
                if isinstance(v3_by_level.get(level), dict)
                else None
                for level in SCORABLE_LEVELS
            ]
            v3_all_six = all(_is_finite_score(score) for score in v3_scores)
            if _is_finite_score(v3_headline) != v3_complete:
                failures.append(
                    "scoring_v3.agent_score must be finite if and only if status is complete"
                )
            if v3_complete != v3_all_six:
                failures.append(
                    "scoring_v3 status is complete if and only if all six scorable levels have scores"
                )
            if v3_complete:
                if v3.get("scored_levels") != 6 or v3.get("required_levels") != 6:
                    failures.append(
                        "complete scoring_v3 run must have scored_levels == required_levels == 6"
                    )
                if _is_finite_score(v3_headline) and v3_all_six:
                    reconstructed_v3 = sum(v3_scores) / len(v3_scores)
                    if abs(v3_headline - reconstructed_v3) >= 1e-9:
                        failures.append(
                            "scoring_v3.agent_score mean invariant failed: "
                            f"got {v3_headline!r}, expected {reconstructed_v3!r}"
                        )

            task_data = v3.get("task_data")
            if not isinstance(task_data, dict):
                failures.append("scoring_v3.task_data must be an object")
            elif task_data.get("join_needed") is True:
                for name in ("benchmark_sha", "task_file", "task_file_sha256"):
                    if not task_data.get(name):
                        failures.append(
                            f"scoring_v3.task_data.{name} required when join_needed is true"
                        )

    # Historical v2-only and v2+v3 summaries remain readable. When v4 is
    # present, its denominator is a literal version contract, not a data-driven
    # decision, and its five-level mean is reconstructed independently.
    v4 = summary.get("scoring_v4")
    if v4 is not None:
        if not isinstance(v4, dict):
            failures.append("scoring_v4 must be an object")
        else:
            if not isinstance(v3, dict):
                failures.append("scoring_v4 requires the scoring_v3 block")
            if v4.get("scoring_version") != SCORING_VERSION_V4:
                failures.append(
                    f"scoring_v4.scoring_version mismatch: expected {SCORING_VERSION_V4!r}, "
                    f"got {v4.get('scoring_version')!r}"
                )
            if v4.get("headline_levels") != list(V4_HEADLINE_LEVELS):
                failures.append(
                    "scoring_v4.headline_levels must be exactly "
                    f"{list(V4_HEADLINE_LEVELS)!r}"
                )
            if v4.get("excluded_levels") != list(V4_EXCLUDED_LEVELS):
                failures.append(
                    "scoring_v4.excluded_levels must be exactly "
                    f"{list(V4_EXCLUDED_LEVELS)!r}"
                )

            v4_by_level = v4.get("by_level")
            if not isinstance(v4_by_level, dict):
                failures.append("scoring_v4.by_level must be an object")
                v4_by_level = {}
            for level, result in v4_by_level.items():
                if level not in ALL_LEVELS or not isinstance(result, dict):
                    failures.append(f"scoring_v4 invalid level entry: {level!r}")
                    continue
                _check_score(result.get("score"), f"scoring_v4.{level}.score", failures)
            if isinstance(v3, dict) and v4_by_level != v3.get("by_level"):
                failures.append(
                    "scoring_v4.by_level must preserve the full scoring_v3 level matrix"
                )

            v4_headline = v4.get("agent_score")
            _check_score(v4_headline, "scoring_v4.agent_score", failures)
            v4_status = v4.get("agent_score_status")
            if v4_status not in {"complete", "incomplete"}:
                failures.append(
                    "scoring_v4.agent_score_status must be 'complete' or 'incomplete'"
                )
            v4_scores = [
                (v4_by_level.get(level) or {}).get("score")
                if isinstance(v4_by_level.get(level), dict)
                else None
                for level in V4_HEADLINE_LEVELS
            ]
            v4_scored = sum(_is_finite_score(score) for score in v4_scores)
            v4_complete = v4_status == "complete"
            v4_all_five = v4_scored == len(V4_HEADLINE_LEVELS)
            if _is_finite_score(v4_headline) != v4_complete:
                failures.append(
                    "scoring_v4.agent_score must be finite if and only if status is complete"
                )
            if v4_complete != v4_all_five:
                failures.append(
                    "scoring_v4 status is complete if and only if all five headline levels have scores"
                )
            if v4.get("scored_levels") != v4_scored:
                failures.append(
                    f"scoring_v4.scored_levels must equal {v4_scored}"
                )
            if v4.get("required_levels") != len(V4_HEADLINE_LEVELS):
                failures.append("scoring_v4.required_levels must equal 5")
            if _is_finite_score(v4_headline) and v4_all_five:
                reconstructed_v4 = sum(v4_scores) / len(v4_scores)
                if abs(v4_headline - reconstructed_v4) >= 1e-9:
                    failures.append(
                        "scoring_v4.agent_score mean invariant failed: "
                        f"got {v4_headline!r}, expected {reconstructed_v4!r}"
                    )

            denominators = summary.get("headline_denominators")
            expected_denominators = {
                SCORING_VERSION: list(SCORABLE_LEVELS),
                SCORING_VERSION_V3: list(SCORABLE_LEVELS),
                SCORING_VERSION_V4: list(V4_HEADLINE_LEVELS),
            }
            if denominators != expected_denominators:
                failures.append(
                    "headline_denominators must spell out the exact v2, v3, and v4 level sets"
                )

    return failures, warnings


def parse_args(argv=None):
    parser = _ArgumentParser(
        description=__doc__,
        epilog=EXIT_CODE_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--results-dir", help="Path to language/<agent-track>")
    parser.add_argument("--model", help="Model name used to build results path")
    parser.add_argument("--timestamp", help="Evaluation timestamp used to build results path")
    parser.add_argument("--track", help="Agent track folder under language/ (default: agent)")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    try:
        results_dir = _results_dir_from_args(parse_args(argv))
        _preflight_results_dir(results_dir)
        failures, warnings = validate_results_dir(results_dir)
    except Exception as exc:
        print(f"{PREFIX} ERROR {type(exc).__name__}: {exc}")
        return 2
    for warning in warnings:
        print(f"{PREFIX} WARN {warning}")
    if failures:
        for failure in failures:
            print(f"{PREFIX} FAIL {failure}")
        print(f"{PREFIX} FAILED {results_dir} ({len(failures)} error(s))")
        return 1
    print(f"{PREFIX} PASS {results_dir} ({len(warnings)} warning(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
