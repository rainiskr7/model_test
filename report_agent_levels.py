#!/usr/bin/env python3
"""저장된 agent summary에서 모델별 대표 run의 레벨 점수를 보고한다."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


LOG_PREFIX = "[agent-levels]"
LEVELS = ("L1", "L2", "L3", "L4", "L5", "L6")
DIAGNOSTIC_KEYS = (
    "l3_retry_inflation",
    "l5_ceiling",
    "swallowed_exception_diagnostics",
    "possible_absorbed_request_timeout_diagnostics",
    "l7_partial_coverage_diagnostics",
)
HARNESS_CONDITION_FIELDS = (
    "model",
    "request_timeout",
    "task_timeout",
    "max_retries",
    "max_tokens",
    "native_tool_calling",
    "sdk_max_retries",
    "openai_sdk_version",
)
LEVEL_CAVEATS = {
    "L1": "-",
    "L2": "representative-run score distribution shown below",
    "L3": "cache-miss propagation via retry inflation",
    "L4": "excluded; measures fixture coverage",
    "L5": "structural ceiling is read from each selected artifact",
    "L6": "polarity corrected in the current scoring contract",
}


def _load_scoring_contract(root_dir: Path):
    scoring_dir = (
        root_dir / "foundation_model_test_non_thinking" / "shared" / "agent" / "scoring"
    )
    sys.path.insert(0, str(scoring_dir))
    try:
        from aggregate import V4_HEADLINE_LEVELS
        from level_spec import LEVEL_SPECS
    finally:
        sys.path.remove(str(scoring_dir))
    return LEVEL_SPECS, V4_HEADLINE_LEVELS


@dataclass(frozen=True)
class Run:
    model: str
    summary_path: Path
    timestamp: str
    timestamp_key: float
    scores: tuple[float, ...]
    task_counts: tuple[int, ...]
    request_timeout: object
    harness_conditions: tuple[object, ...] | None
    deaths: tuple[tuple[str, str], ...]
    contamination_bounds: tuple[tuple[str, object, object], ...]
    diagnostics: dict[str, object]
    l7_result_field_score: float | None
    l7_scored_tasks: int | None
    l7_total_tasks: int | None

    @property
    def clean(self) -> bool:
        return not self.deaths

    @property
    def note(self) -> str:
        return "; ".join(
            f"{level} {task_id} infra death" for level, task_id in self.deaths
        )

    @property
    def bounds_text(self) -> str:
        def render(value: object) -> str:
            return f"{float(value):.3f}" if _is_score(value) else "null"

        return "; ".join(
            f"{level}[as-zero={render(as_zero)},exclude={render(excluded)}]"
            for level, as_zero, excluded in self.contamination_bounds
        )


@dataclass(frozen=True)
class RepeatGroup:
    model: str
    conditions: tuple[object, ...]
    runs: tuple[Run, ...]


def _log(message: str, *, file=None) -> None:
    print(f"{LOG_PREFIX} {message}", file=file or sys.stdout)


def _parse_timestamp(value: object, fallback: float) -> tuple[str, float]:
    if not isinstance(value, str) or not value:
        return "-", fallback
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        shown = parsed.isoformat(timespec="seconds")
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        key = parsed.timestamp()
        shown = shown.replace("+00:00", "Z")
        return shown, key
    except ValueError:
        return value, fallback


def _is_score(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _uniform_harness_conditions(
    model: str, metadata_by_level: dict[str, dict]
) -> tuple[object, ...] | None:
    recorded = []
    for level in LEVELS:
        metadata = metadata_by_level.get(level) or {}
        if not all(field in metadata for field in HARNESS_CONDITION_FIELDS):
            return None
        values = tuple(metadata[field] for field in HARNESS_CONDITION_FIELDS)
        if values[0] != model:
            return None
        recorded.append(values)
    if any(values != recorded[0] for values in recorded[1:]):
        return None
    return recorded[0]


def _load_run(summary_path: Path) -> Run | None:
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    model = summary.get("model")
    by_level = (summary.get("scoring_v4") or {}).get("by_level") or {}
    if not isinstance(model, str) or not model:
        return None

    scores = tuple((by_level.get(level) or {}).get("score") for level in LEVELS)
    # 부분 run은 모델별 L1~L6 표의 대표 후보가 아니다.
    if not all(_is_score(score) for score in scores):
        return None

    timestamps = []
    request_timeout = None
    deaths = []
    contamination_bounds = []
    metadata_by_level = {}
    raw_by_level = {}
    error_by_level = (
        (summary.get("infrastructure_error_diagnostics") or {}).get("by_level")
        or {}
    )
    for level in LEVELS:
        diagnostic = error_by_level.get(level) or {}
        bounds = diagnostic.get("score_bounds") or {}
        if diagnostic.get("infrastructure_error_task_count", 0) <= 0:
            continue
        if not isinstance(bounds, dict):
            continue
        contamination_bounds.append(
            (
                level,
                bounds.get("with_infrastructure_error_tasks_scored_as_zero"),
                bounds.get("with_infrastructure_error_tasks_excluded"),
            )
        )
    level_paths = sorted(
        summary_path.parent.glob("L*.json"),
        key=lambda path: int(path.stem[1:]) if path.stem[1:].isdigit() else 10_000,
    )
    present_levels = {path.stem for path in level_paths}
    if not set(LEVELS).issubset(present_levels):
        return None
    for level_path in level_paths:
        level = level_path.stem
        if not level[1:].isdigit():
            continue
        raw = json.loads(level_path.read_text(encoding="utf-8"))
        raw_by_level[level] = raw
        metadata = raw.get("metadata") or {}
        metadata_by_level[level] = metadata
        timestamp = metadata.get("timestamp")
        if isinstance(timestamp, str) and timestamp:
            timestamps.append(timestamp)
        if request_timeout is None and metadata.get("request_timeout") is not None:
            request_timeout = metadata["request_timeout"]
        for task in raw.get("results") or []:
            if isinstance(task, dict) and task.get("error") is not None:
                task_id = task.get("task_id")
                deaths.append((level, str(task_id or "unknown-task")))

    task_counts = tuple(len((raw_by_level[level].get("results") or [])) for level in LEVELS)
    l7_metric = (
        (((by_level.get("L7") or {}).get("metrics") or {}).get("ResultFieldCoverage_det"))
        or {}
    )
    l7_score = l7_metric.get("score")
    l7_scored = l7_metric.get("n_scored")
    l7_total = len(raw_by_level["L7"].get("results") or []) if "L7" in raw_by_level else None
    fallback = summary_path.stat().st_mtime
    timestamp, timestamp_key = _parse_timestamp(
        min(timestamps) if timestamps else None, fallback
    )
    return Run(
        model=model,
        summary_path=summary_path,
        timestamp=timestamp,
        timestamp_key=timestamp_key,
        scores=tuple(float(score) for score in scores),
        task_counts=task_counts,
        request_timeout=request_timeout,
        harness_conditions=_uniform_harness_conditions(model, metadata_by_level),
        deaths=tuple(deaths),
        contamination_bounds=tuple(contamination_bounds),
        diagnostics={key: summary.get(key) for key in DIAGNOSTIC_KEYS},
        l7_result_field_score=float(l7_score) if _is_score(l7_score) else None,
        l7_scored_tasks=int(l7_scored) if _is_score(l7_scored) else None,
        l7_total_tasks=int(l7_total) if _is_score(l7_total) else None,
    )


def load_runs(results_root: Path) -> list[Run]:
    runs = []
    for summary_path in sorted(results_root.rglob("summary.json")):
        if summary_path.parent.parent.name != "language":
            continue
        if not summary_path.parent.name.startswith("agent"):
            continue
        run = _load_run(summary_path)
        if run is not None:
            runs.append(run)
    return runs


def select_runs(all_runs: Sequence[Run]) -> list[Run]:
    candidates: dict[str, list[Run]] = {}
    for run in all_runs:
        candidates.setdefault(run.model, []).append(run)

    selected = []
    for model_runs in candidates.values():
        clean_runs = [run for run in model_runs if run.clean]
        pool = clean_runs or model_runs
        selected.append(
            max(pool, key=lambda run: (run.timestamp_key, str(run.summary_path)))
        )
    return sorted(selected, key=lambda run: run.model)


def find_repeat_groups(all_runs: Sequence[Run]) -> list[RepeatGroup]:
    grouped: dict[tuple[object, ...], list[Run]] = {}
    for run in all_runs:
        # _load_run을 통과한 L1~L6 완전 run만 여기 도달한다.
        if run.harness_conditions is not None:
            grouped.setdefault(run.harness_conditions, []).append(run)
    repeat_groups = [
        RepeatGroup(
            model=runs[0].model,
            conditions=conditions,
            runs=tuple(sorted(runs, key=lambda run: run.timestamp_key)),
        )
        for conditions, runs in grouped.items()
        if len(runs) > 1
    ]
    return sorted(repeat_groups, key=lambda group: (group.model, repr(group.conditions)))


def _format_distribution(values: Sequence[object], render) -> str:
    counts = Counter(values)
    return ", ".join(
        f"{render(value)}×{count}"
        for value, count in sorted(counts.items(), key=lambda item: item[0])
    )


def _variance_shares(runs: Sequence[Run], headline_levels: Sequence[str]) -> dict[str, float]:
    variances = {
        level: statistics.pvariance(run.scores[LEVELS.index(level)] for run in runs)
        for level in headline_levels
    }
    total = sum(variances.values())
    if total == 0:
        return {level: 0.0 for level in headline_levels}
    return {level: variance / total for level, variance in variances.items()}


def _nonzero_payload(value: object, *, inside_list: bool = False) -> object | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return value if value != 0 else None
    if isinstance(value, str):
        return value if inside_list and value else None
    if isinstance(value, list):
        kept = [
            child
            for item in value
            if (child := _nonzero_payload(item, inside_list=True)) is not None
        ]
        return kept or None
    if isinstance(value, dict):
        kept = {
            key: child
            for key, item in value.items()
            if (child := _nonzero_payload(item, inside_list=inside_list)) is not None
        }
        return kept or None
    return None


def _diagnostic_payload(key: str, diagnostic: object) -> object | None:
    if not isinstance(diagnostic, dict):
        return None
    if key == "swallowed_exception_diagnostics":
        if not _is_score(diagnostic.get("matching_task_count")) or diagnostic["matching_task_count"] <= 0:
            return None
        diagnostic = {
            "matching_task_count": diagnostic.get("matching_task_count"),
            "by_level": diagnostic.get("by_level"),
        }
    elif key == "possible_absorbed_request_timeout_diagnostics":
        if not _is_score(diagnostic.get("positive_count")) or diagnostic["positive_count"] <= 0:
            return None
        diagnostic = {
            "positive_count": diagnostic.get("positive_count"),
            "positives": diagnostic.get("positives"),
        }
    elif key == "l7_partial_coverage_diagnostics":
        diagnostic = {
            "distribution": diagnostic.get("distribution"),
            "totals": diagnostic.get("totals"),
            "coverage": diagnostic.get("coverage"),
        }
    return _nonzero_payload(diagnostic)


def _print_diagnostics(runs: Sequence[Run]) -> None:
    _log("DIAGNOSTICS selected runs (non-zero stored values)")
    for run in runs:
        emitted = False
        zero_or_absent = []
        for key in DIAGNOSTIC_KEYS:
            payload = _diagnostic_payload(key, run.diagnostics.get(key))
            if payload is None:
                zero_or_absent.append(key)
                continue
            rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            _log(f"{run.model} {run.timestamp} {key}={rendered}")
            emitted = True
        if not emitted:
            _log(
                f"{run.model} {run.timestamp} diagnostics: all five zero/absent "
                f"({','.join(DIAGNOSTIC_KEYS)})"
            )
        elif zero_or_absent:
            _log(
                f"{run.model} {run.timestamp} diagnostics zero/absent="
                f"{','.join(zero_or_absent)}"
            )


def _print_l7_conclusion(runs: Sequence[Run]) -> None:
    available = [run for run in runs if run.l7_result_field_score is not None]
    _log("L7 RESULT_FIELD_COVERAGE")
    if len(available) != len(runs):
        _log(
            f"available={len(available)}/{len(runs)}; promotion=no; "
            "criterion=every selected run must expose the metric, every raw task must be "
            "scorable, and the metric must separate models"
        )
        return
    scores = [run.l7_result_field_score for run in available]
    assert all(score is not None for score in scores)
    numeric_scores = [float(score) for score in scores]
    spread = max(numeric_scores) - min(numeric_scores)
    fully_applicable = all(
        run.l7_scored_tasks is not None
        and run.l7_total_tasks is not None
        and run.l7_scored_tasks == run.l7_total_tasks
        for run in available
    )
    separates_models = spread > 0
    promoted = fully_applicable and separates_models
    scored_distribution = _format_distribution(
        [f"{run.l7_scored_tasks}/{run.l7_total_tasks}" for run in available], str
    )
    score_distribution = _format_distribution(numeric_scores, lambda value: f"{value:.6f}")
    _log(
        f"scores={score_distribution}; min={min(numeric_scores):.6f}; "
        f"max={max(numeric_scores):.6f}; spread={spread:.6f}; "
        f"scored_tasks={scored_distribution}; fully_applicable={'yes' if fully_applicable else 'no'}; "
        f"separates_models={'yes' if separates_models else 'no'}; promotion={'yes' if promoted else 'no'}"
    )
    _log(
        "criterion=every selected run must expose the metric, every raw task must be "
        "scorable, and the metric must separate models"
    )


def print_report(
    runs: Sequence[Run],
    repeat_groups: Sequence[RepeatGroup],
    level_specs: dict,
    headline_levels: Sequence[str],
) -> None:
    repeat_count_by_model: dict[str, int] = {}
    for group in repeat_groups:
        repeat_count_by_model[group.model] = max(
            repeat_count_by_model.get(group.model, 0), len(group.runs)
        )

    model_width = max(len("model"), *(len(run.model) for run in runs))
    header = (
        f"{'model':<{model_width}}  {'run_timestamp':<20}  "
        f"{'L1':>5}  {'L2':>5}  {'L3':>5}  {'L4(observation)':>20}  "
        f"{'L5':>5}  {'L6(observation)':>20}  "
        f"{'request_timeout':>15}  contamination_bounds(as-zero/exclude)  note"
    )
    _log(header)
    for run in runs:
        timeout = "-" if run.request_timeout is None else str(run.request_timeout)
        observation = (
            f"repeat:{repeat_count_by_model[run.model]}"
            if run.model in repeat_count_by_model
            else "single"
        )
        cells = []
        for level, score in zip(LEVELS, run.scores):
            rendered = f"{score:.3f}"
            if level in {"L4", "L6"}:
                rendered = f"{rendered}[{observation}]"
                cells.append(f"{rendered:>20}")
            else:
                cells.append(f"{rendered:>5}")
        row = (
            f"{run.model:<{model_width}}  {run.timestamp:<20}  {'  '.join(cells)}  "
            f"{timeout:>15}  {run.bounds_text or '-'}  {run.note}"
        )
        _log(row.rstrip())
    _log(
        "L4/L6 tags: [single] is one observation; [repeat:n] has a matching-condition "
        "repeat group. Use the computed repeat spreads below when comparing cells."
    )

    variance_shares = _variance_shares(runs, headline_levels)
    _log("CONTEXT (all measured values derived from selected artifacts)")
    _log(
        f"{'level':<5}  {'raw_tasks(value×runs)':<24}  {'in_score_metrics':>16}  "
        f"{'min':>8}  {'max':>8}  {'spread':>8}  {'v4_variance_share':>18}  caveat"
    )
    for index, level in enumerate(LEVELS):
        values = [run.scores[index] for run in runs]
        task_distribution = _format_distribution(
            [run.task_counts[index] for run in runs], str
        )
        metric_count = sum(spec.in_score for spec in level_specs[level])
        share = (
            f"{variance_shares[level]:.3%}" if level in variance_shares else "excluded"
        )
        caveat = LEVEL_CAVEATS[level]
        if level == "L2":
            caveat += "; scores=" + _format_distribution(
                values, lambda value: f"{value:.3f}"
            )
        if level == "L5":
            ceilings = [
                diagnostic.get("level_ceiling")
                for run in runs
                if isinstance((diagnostic := run.diagnostics.get("l5_ceiling")), dict)
                and _is_score(diagnostic.get("level_ceiling"))
            ]
            caveat += "; level_ceiling=" + (
                _format_distribution(ceilings, lambda value: f"{value:.3f}")
                if ceilings
                else "absent"
            )
        _log(
            f"{level:<5}  {task_distribution:<24}  {metric_count:>16}  "
            f"{min(values):>8.3f}  {max(values):>8.3f}  "
            f"{max(values) - min(values):>8.3f}  {share:>18}  {caveat}"
        )

    _log("REPEAT SPREADS (complete runs with identical recorded harness conditions)")
    if not repeat_groups:
        _log("no repeat group exists")
    for group_index, group in enumerate(repeat_groups, start=1):
        for index, level in enumerate(LEVELS):
            values = [run.scores[index] for run in group.runs]
            _log(
                f"{level} model={group.model} group={group_index} runs={len(group.runs)} "
                f"min={min(values):.3f} max={max(values):.3f} "
                f"spread={max(values) - min(values):.3f}"
            )

    _print_l7_conclusion(runs)
    _print_diagnostics(runs)
    _log(f"PASS models={len(runs)}")


def main(argv: Sequence[str] | None = None) -> int:
    root_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="저장된 agent run에서 모델별 L1~L6 점수를 보고합니다."
    )
    parser.add_argument(
        "--results-root",
        type=Path,
        default=root_dir / "foundation_model_test_non_thinking" / "results",
        help="검색할 results 디렉터리",
    )
    args = parser.parse_args(argv)

    if not args.results_root.is_dir():
        _log(f"FAIL results root not found: {args.results_root}", file=sys.stderr)
        return 1
    try:
        level_specs, headline_levels = _load_scoring_contract(root_dir)
        all_runs = load_runs(args.results_root)
    except (OSError, json.JSONDecodeError, TypeError, ImportError) as exc:
        _log(f"FAIL could not read stored summaries: {exc}", file=sys.stderr)
        return 1
    runs = select_runs(all_runs)
    if not runs:
        _log(f"FAIL no complete L1-L6 agent summaries under {args.results_root}", file=sys.stderr)
        return 1
    print_report(runs, find_repeat_groups(all_runs), level_specs, headline_levels)
    return 0


if __name__ == "__main__":
    sys.exit(main())
