#!/usr/bin/env python3
"""저장된 agent summary에서 모델별 대표 run의 레벨 점수를 보고한다."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


LOG_PREFIX = "[agent-levels]"
LEVELS = ("L1", "L2", "L3", "L4", "L5", "L6")
LEVEL_CONTEXT = {
    # caveat 뒤의 repeat spread 는 동일 조건 3회 반복 실측치다
    # (qwen_qwen3.5_35b_a3b_fp8, request_timeout=120/task_timeout=600, 2026-08-17~18).
    # 서빙 계층이 greedy 에서도 출력을 바꾸므로 spread 가 큰 레벨은 단일 run 비교에 쓰지 않는다.
    "L1": (11, 3, "repeat spread 0.000"),
    "L2": (15, 1, "saturated (9 models: 7x0.933, 2x0.867); repeat spread 0.000"),
    "L3": (10, 3, "cache-miss propagation via retry inflation; repeat spread 0.000"),
    "L4": (10, 2, "excluded; measures fixture coverage; repeat spread 0.123 - not single-run comparable"),
    "L5": (20, 3, "structural ceiling 0.667; repeat spread 0.022"),
    "L6": (15, 2, "polarity corrected in v3; repeat spread 0.065 - not single-run comparable"),
}


@dataclass(frozen=True)
class Run:
    model: str
    summary_path: Path
    timestamp: str
    timestamp_key: float
    scores: tuple[float, ...]
    request_timeout: object
    deaths: tuple[tuple[str, str], ...]
    contamination_bounds: tuple[tuple[str, object, object], ...]

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
        metadata = raw.get("metadata") or {}
        timestamp = metadata.get("timestamp")
        if isinstance(timestamp, str) and timestamp:
            timestamps.append(timestamp)
        if request_timeout is None and metadata.get("request_timeout") is not None:
            request_timeout = metadata["request_timeout"]
        for task in raw.get("results") or []:
            if isinstance(task, dict) and task.get("error") is not None:
                task_id = task.get("task_id")
                deaths.append((level, str(task_id or "unknown-task")))

    fallback = summary_path.stat().st_mtime
    timestamp, timestamp_key = _parse_timestamp(min(timestamps) if timestamps else None, fallback)
    return Run(
        model=model,
        summary_path=summary_path,
        timestamp=timestamp,
        timestamp_key=timestamp_key,
        scores=tuple(float(score) for score in scores),
        request_timeout=request_timeout,
        deaths=tuple(deaths),
        contamination_bounds=tuple(contamination_bounds),
    )


def select_runs(results_root: Path) -> list[Run]:
    candidates: dict[str, list[Run]] = {}
    for summary_path in sorted(results_root.rglob("summary.json")):
        if summary_path.parent.parent.name != "language":
            continue
        if not summary_path.parent.name.startswith("agent"):
            continue
        run = _load_run(summary_path)
        if run is not None:
            candidates.setdefault(run.model, []).append(run)

    selected = []
    for model, model_runs in candidates.items():
        clean_runs = [run for run in model_runs if run.clean]
        pool = clean_runs or model_runs
        selected.append(
            max(pool, key=lambda run: (run.timestamp_key, str(run.summary_path)))
        )
    return sorted(selected, key=lambda run: run.model)


def print_report(runs: Sequence[Run]) -> None:
    model_width = max(len("model"), *(len(run.model) for run in runs))
    header = (
        f"{'model':<{model_width}}  {'run_timestamp':<20}  "
        f"{'L1':>5}  {'L2':>5}  {'L3':>5}  {'L4':>5}  {'L5':>5}  {'L6':>5}  "
        f"{'request_timeout':>15}  contamination_bounds(as-zero/exclude)  note"
    )
    _log(header)
    for run in runs:
        timeout = "-" if run.request_timeout is None else str(run.request_timeout)
        scores = "  ".join(f"{score:5.3f}" for score in run.scores)
        row = (
            f"{run.model:<{model_width}}  {run.timestamp:<20}  {scores}  "
            f"{timeout:>15}  {run.bounds_text or '-'}  {run.note}"
        )
        _log(row.rstrip())

    _log("CONTEXT")
    _log(f"{'level':<5}  {'tasks':>5}  {'metrics':>7}  caveat")
    for level in LEVELS:
        tasks, metrics, caveat = LEVEL_CONTEXT[level]
        _log(f"{level:<5}  {tasks:>5}  {metrics:>7}  {caveat}")
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
        runs = select_runs(args.results_root)
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        _log(f"FAIL could not read stored summaries: {exc}", file=sys.stderr)
        return 1
    if not runs:
        _log(f"FAIL no complete L1-L6 agent summaries under {args.results_root}", file=sys.stderr)
        return 1
    print_report(runs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
