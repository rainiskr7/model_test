"""CLI for deterministic Ko-AgentBench agent scoring."""

import argparse
import json
import math
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

if __package__:
    from . import SCORING_VERSION
    from .context import BenchDriftError, build_eval_context, load_vendored_metric
    from . import extra_metrics
    from .data_health import build_data_health
    from .level_spec import (
        COMMON_RECORD_ONLY,
        JUDGE_METRICS,
        LEVEL_SPECS,
        PASSK_PRIMARY_METRICS,
        MetricSpec,
        level_score,
        mean_or_none,
    )
    from .result_shape import has_repetition_records as _has_repetition_records
    from .task_source import bench_pin, load_bench_tasks
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from __init__ import SCORING_VERSION
    import extra_metrics
    from data_health import build_data_health
    from context import BenchDriftError, build_eval_context, load_vendored_metric
    from level_spec import (
        COMMON_RECORD_ONLY,
        JUDGE_METRICS,
        LEVEL_SPECS,
        PASSK_PRIMARY_METRICS,
        MetricSpec,
        level_score,
        mean_or_none,
    )
    from result_shape import has_repetition_records as _has_repetition_records
    from task_source import bench_pin, load_bench_tasks


PREFIX = "[agent-scoring]"
ALL_LEVELS = tuple(f"L{i}" for i in range(1, 8))


def _safe_model_name(model: str) -> str:
    return model.replace("/", "_").replace("-", "_").replace(":", "_")


def _fmt(value: Optional[float]) -> str:
    return "null" if value is None else f"{value:.3f}"


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
        / _safe_model_name(args.model)
        / args.timestamp
        / "language"
        / args.track
    )


def _load_level(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _tasks(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    tasks = data.get("results")
    if isinstance(tasks, list):
        return tasks
    tasks = data.get("tasks")
    if isinstance(tasks, list):
        return tasks
    return []


def _merged_repetition_record(task: Dict[str, Any], record: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(task)
    merged.pop("repetition_records", None)
    merged.update(record)
    return merged


def _population_std(values: List[float]) -> Optional[float]:
    if not values:
        return None
    mean = sum(values) / len(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / len(values))


def _average_metric(
    tasks: List[Dict[str, Any]],
    spec: MetricSpec,
    bench_tasks: Optional[Dict[str, dict]] = None,
    scored_ids: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    scores = []
    errors = []
    repeated_by_index: List[List[float]] = []
    repeated_seen = False
    for task in tasks:
        try:
            bench_task = None
            if bench_tasks is not None:
                task_id = task.get("task_id")
                bench_task = bench_tasks.get(str(task_id))
                if bench_task is None:
                    raise RuntimeError(f"bench task not found for task_id={task_id}")
            if _has_repetition_records(task):
                repeated_seen = True
                repeated_scores = []
                for index, record in enumerate(task["repetition_records"]):
                    ctx = build_eval_context(_merged_repetition_record(task, record), bench_task)
                    score = spec.producer(ctx)
                    if score is not None:
                        value = float(score)
                        repeated_scores.append(value)
                        while len(repeated_by_index) <= index:
                            repeated_by_index.append([])
                        repeated_by_index[index].append(value)
                score = mean_or_none(repeated_scores)
                if score is not None:
                    scores.append(float(score))
                    if scored_ids is not None and spec.in_score:
                        scored_ids.add(str(task.get("task_id")))
                    continue
                continue

            ctx = build_eval_context(task, bench_task)
            score = spec.producer(ctx)
        except BenchDriftError as exc:
            errors.append(f"{task.get('task_id')}: {type(exc).__name__}: {exc}")
            continue
        except Exception as exc:
            return {
                "score": None,
                "status": "error",
                "in_score": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
        if score is not None:
            scores.append(float(score))
            if scored_ids is not None and spec.in_score:
                scored_ids.add(str(task.get("task_id")))

    if errors:
        return {
            "score": None,
            "status": "error",
            "in_score": spec.in_score,
            "error": "; ".join(errors),
        }

    entry = {
        "score": mean_or_none(scores),
        "status": "ok" if scores else "not_applicable",
        "in_score": spec.in_score,
        "n_tasks": len(scores),
    }
    if repeated_seen:
        per_repetition = [
            mean_or_none(values)
            for values in repeated_by_index
            if mean_or_none(values) is not None
        ]
        entry.update({
            "repeated": True,
            "n_repetitions": len(per_repetition),
            "std": _population_std(per_repetition),
            "per_repetition": per_repetition,
        })
    return entry


def _judge_entry() -> Dict[str, Any]:
    return {"score": None, "status": "judge_missing", "in_score": False}


def _pass_at_k_entry(
    tasks: List[Dict[str, Any]], bench_tasks: Optional[Dict[str, dict]] = None
) -> Dict[str, Any]:
    if not any(len(task.get("repetition_results", []) or []) >= 2 for task in tasks):
        return {
            "score": None,
            "status": "not_applicable",
            "in_score": False,
            "reason": "repetition_results length < 2",
            "note": "runner survival signal, not correctness - see PassK_det",
        }
    entry = _average_metric(tasks, MetricSpec("pass@k", _vendored("pass@k"), False), bench_tasks)
    entry["note"] = "runner survival signal, not correctness - see PassK_det"
    return entry


def _passk_det_entry(
    level: str,
    tasks: List[Dict[str, Any]],
    bench_tasks: Optional[Dict[str, dict]] = None,
) -> Dict[str, Any]:
    primary_name = PASSK_PRIMARY_METRICS[level]
    primary_spec = next((spec for spec in LEVEL_SPECS[level] if spec.name == primary_name), None)
    if primary_spec is None:
        return {
            "score": None,
            "status": "error",
            "in_score": False,
            "error": f"primary metric not configured: {primary_name}",
        }

    repeated_tasks = [task for task in tasks if _has_repetition_records(task)]
    if not repeated_tasks:
        return {
            "score": None,
            "status": "not_applicable",
            "in_score": False,
            "reason": "repetition_records missing",
            "primary_metric": primary_name,
        }

    passed = 0
    evaluated = 0
    k = 0
    for task in repeated_tasks:
        task_id = task.get("task_id")
        bench_task = bench_tasks.get(str(task_id)) if bench_tasks is not None else None
        if bench_tasks is not None and bench_task is None:
            return {
                "score": None,
                "status": "error",
                "in_score": False,
                "error": f"bench task not found for task_id={task_id}",
                "primary_metric": primary_name,
            }

        task_scores = []
        for record in task["repetition_records"]:
            try:
                ctx = build_eval_context(_merged_repetition_record(task, record), bench_task)
                score = primary_spec.producer(ctx)
            except Exception as exc:
                return {
                    "score": None,
                    "status": "error",
                    "in_score": False,
                    "error": f"{type(exc).__name__}: {exc}",
                    "primary_metric": primary_name,
                }
            if score is not None:
                task_scores.append(float(score))

        if not task_scores:
            continue
        evaluated += 1
        k = max(k, len(task_scores))
        if any(score == 1.0 for score in task_scores):
            passed += 1

    if evaluated == 0:
        return {
            "score": None,
            "status": "not_applicable",
            "in_score": False,
            "reason": "no scorable repetition_records",
            "primary_metric": primary_name,
        }

    return {
        "score": passed / evaluated,
        "status": "ok",
        "in_score": False,
        "primary_metric": primary_name,
        "k": k,
    }


def _resp_ok_entry(
    tasks: List[Dict[str, Any]], bench_tasks: Optional[Dict[str, dict]] = None
) -> Dict[str, Any]:
    if all((task.get("resp_schema") or {}).get("type") == "string" for task in tasks):
        return {
            "score": None,
            "status": "not_applicable",
            "in_score": False,
            "reason": "resp_schema.type == string",
        }
    return _average_metric(tasks, MetricSpec("RespOK", _vendored("RespOK"), False), bench_tasks)


def _vendored(name: str):
    def _evaluate(ctx):
        return load_vendored_metric(name).evaluate(ctx).score

    return _evaluate


def score_level(
    level: str,
    data: Dict[str, Any],
    bench_tasks: Optional[Dict[str, dict]] = None,
) -> Dict[str, Any]:
    tasks = _tasks(data)
    entries: Dict[str, Dict[str, Any]] = {}
    if bench_tasks is None and tasks:
        bench_tasks = load_bench_tasks(level)

    scored_ids: Set[str] = set()
    for spec in LEVEL_SPECS[level]:
        entries[spec.name] = _average_metric(tasks, spec, bench_tasks, scored_ids=scored_ids)

    for metric_name in JUDGE_METRICS:
        entries[metric_name] = _judge_entry()

    for metric_name in COMMON_RECORD_ONLY:
        if metric_name == "pass@k":
            entries[metric_name] = _pass_at_k_entry(tasks, bench_tasks)
        elif metric_name == "RespOK":
            entries[metric_name] = _resp_ok_entry(tasks, bench_tasks)

    entries["PassK_det"] = _passk_det_entry(level, tasks, bench_tasks)

    return {
        "total": len(tasks),
        "scored_tasks": len(scored_ids),
        "score": level_score(entries),
        "metrics": entries,
    }


def _native_tool_calling(level_data: Iterable[Dict[str, Any]]):
    for data in level_data:
        metadata = data.get("metadata") or {}
        if "native_tool_calling" in metadata:
            return metadata.get("native_tool_calling")
    return None


def _model_name(results_dir: Path, level_data: Iterable[Dict[str, Any]]) -> str:
    for data in level_data:
        metadata = data.get("metadata") or {}
        if metadata.get("model"):
            return _safe_model_name(str(metadata["model"]))
    try:
        return results_dir.parents[2].name
    except IndexError:
        return ""


def build_summary_from_loaded(
    loaded: Dict[str, Dict[str, Any]],
    results_dir: Path,
    bench_task_maps: Optional[Dict[str, Dict[str, dict]]] = None,
    bench_pin_value: Optional[dict] = None,
) -> Dict[str, Any]:
    if bench_task_maps is None:
        bench_task_maps = {
            level: load_bench_tasks(level)
            for level, data in loaded.items()
            if _tasks(data)
        }
    by_level = {
        level: score_level(level, data, bench_task_maps.get(level))
        for level, data in loaded.items()
    }
    levels_missing = [level for level in ALL_LEVELS if level not in loaded]
    levels_unscorable = [
        level for level, result in by_level.items()
        if not any(
            entry.get("in_score") and entry.get("score") is not None
            for entry in result.get("metrics", {}).values()
        )
    ]

    level_scores = [
        result["score"]
        for result in by_level.values()
        if result.get("score") is not None
    ]
    weighted_scores = {
        level: int(result["scored_tasks"])
        for level, result in by_level.items()
        if result.get("score") is not None
        and isinstance(result.get("scored_tasks"), int)
        and result.get("scored_tasks") > 0
    }
    weighted_total = sum(weighted_scores.values())
    agent_score = (
        sum(by_level[level]["score"] * total for level, total in weighted_scores.items())
        / weighted_total
        if weighted_total > 0
        else None
    )
    runner_survival_rate = {
        level: data.get("metadata", {}).get("success_rate")
        for level, data in loaded.items()
        if data.get("metadata", {}).get("success_rate") is not None
    }
    runner_survival_rate["note"] = (
        "기존 metadata.success_rate. 정답률이 아니라 'final_response 반환 + step>=1' "
        "생존신호다 (run.py:232-235). 비교용으로 쓰지 말 것."
    )
    data_health = build_data_health(loaded, bench_task_maps, _tasks)
    track = results_dir.name
    level_values = list(loaded.values())
    return {
        "benchmark": "Ko-AgentBench (deterministic scoring)",
        "model": _model_name(results_dir, level_values),
        "track": track,
        "scoring_version": SCORING_VERSION,
        "native_tool_calling": _native_tool_calling(level_values),
        "agent_score": agent_score,
        "agent_score_equal_level": mean_or_none(level_scores),
        "weighting": {"scheme": "scored_task_count", "weights": weighted_scores},
        "data_health": data_health,
        "by_level": by_level,
        "bench_pin": (
            bench_pin_value
            if bench_pin_value is not None
            else bench_pin(loaded.keys()) if loaded else {"tasks_sha256": {}}
        ),
        "runner_survival_rate": runner_survival_rate,
        "levels_missing": levels_missing,
        "levels_unscorable": levels_unscorable,
    }


def build_summary(results_dir: Path) -> Dict[str, Any]:
    if not results_dir.is_dir():
        raise RuntimeError(f"results dir not found: {results_dir}")

    loaded = {}
    for level in ALL_LEVELS:
        path = results_dir / f"{level}.json"
        if path.is_file():
            loaded[level] = _load_level(path)

    return build_summary_from_loaded(loaded, results_dir)


def _bench_pin_drift_keys(old_pin: Optional[dict], new_pin: Optional[dict]) -> List[str]:
    if not isinstance(old_pin, dict) or not isinstance(new_pin, dict):
        return []
    drifted = []
    for key, old_value in old_pin.items():
        if old_value is None or key not in new_pin or new_pin[key] is None:
            continue
        if old_value != new_pin[key]:
            drifted.append(str(key))
    return drifted


def _warn_bench_pin_drift(results_dir: Path, summary: Dict[str, Any]) -> None:
    summary_path = results_dir / "summary.json"
    if not summary_path.is_file():
        return
    try:
        with summary_path.open("r", encoding="utf-8") as f:
            previous = json.load(f)
    except Exception:
        return
    if not isinstance(previous, dict):
        return
    drifted = _bench_pin_drift_keys(previous.get("bench_pin"), summary.get("bench_pin"))
    if drifted:
        print(
            f"{PREFIX} WARNING: bench_pin drift detected for keys: {', '.join(drifted)}",
            file=sys.stderr,
        )


def print_table(summary: Dict[str, Any], skipped_count: int) -> None:
    print(f"{PREFIX} model={summary['model']} track={summary['track']}")
    for level in ALL_LEVELS:
        result = summary["by_level"].get(level)
        if not result:
            continue
        metrics = " ".join(
            f"{name}={_fmt(entry.get('score'))}/{entry.get('status')}"
            for name, entry in result["metrics"].items()
            if entry.get("in_score") or entry.get("score") is not None
        )
        print(f"{PREFIX} {level} total={result['total']} score={_fmt(result['score'])} {metrics}")
    if (summary.get("data_health") or {}).get("no_tool_calls_recorded"):
        print(
            f"{PREFIX} WARNING: no tool_call records in this run - "
            "all deterministic metrics are structurally 0"
        )
    print(f"{PREFIX} agent_score={_fmt(summary['agent_score'])}")
    print(f"{PREFIX} agent_score_equal_level={_fmt(summary['agent_score_equal_level'])}")
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
        _warn_bench_pin_drift(results_dir, summary)
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
