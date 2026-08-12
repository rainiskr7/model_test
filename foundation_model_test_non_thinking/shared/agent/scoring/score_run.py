"""CLI for deterministic Ko-AgentBench agent scoring."""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

if __package__:
    from . import SCORING_VERSION
    from .context import build_eval_context
    from .level_spec import (
        COMMON_RECORD_ONLY,
        JUDGE_METRICS,
        LEVEL_SPECS,
        MetricSpec,
        level_score,
        mean_or_none,
    )
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from __init__ import SCORING_VERSION
    from context import build_eval_context
    from level_spec import (
        COMMON_RECORD_ONLY,
        JUDGE_METRICS,
        LEVEL_SPECS,
        MetricSpec,
        level_score,
        mean_or_none,
    )


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


def _average_metric(tasks: List[Dict[str, Any]], spec: MetricSpec) -> Dict[str, Any]:
    scores = []
    for task in tasks:
        try:
            ctx = build_eval_context(task)
            score = spec.producer(ctx)
        except Exception as exc:
            return {
                "score": None,
                "status": "error",
                "in_score": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
        if score is not None:
            scores.append(float(score))

    return {
        "score": mean_or_none(scores),
        "status": "ok" if scores else "not_applicable",
        "in_score": spec.in_score,
    }


def _judge_entry() -> Dict[str, Any]:
    return {"score": None, "status": "judge_missing", "in_score": False}


def _pass_at_k_entry(tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not any(len(task.get("repetition_results", []) or []) >= 2 for task in tasks):
        return {
            "score": None,
            "status": "not_applicable",
            "in_score": False,
            "reason": "repetition_results length < 2",
        }
    return _average_metric(tasks, MetricSpec("pass@k", _vendored("pass@k"), False))


def _resp_ok_entry(tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
    if all((task.get("resp_schema") or {}).get("type") == "string" for task in tasks):
        return {
            "score": None,
            "status": "not_applicable",
            "in_score": False,
            "reason": "resp_schema.type == string",
        }
    return _average_metric(tasks, MetricSpec("RespOK", _vendored("RespOK"), False))


def _vendored(name: str):
    def _evaluate(ctx):
        try:
            from .context import load_metrics_module
        except ImportError:
            from context import load_metrics_module

        return load_metrics_module().METRICS[name].evaluate(ctx).score

    return _evaluate


def score_level(level: str, data: Dict[str, Any]) -> Dict[str, Any]:
    tasks = _tasks(data)
    entries: Dict[str, Dict[str, Any]] = {}

    for spec in LEVEL_SPECS[level]:
        entries[spec.name] = _average_metric(tasks, spec)

    for metric_name in JUDGE_METRICS:
        entries[metric_name] = _judge_entry()

    for metric_name in COMMON_RECORD_ONLY:
        if metric_name == "pass@k":
            entries[metric_name] = _pass_at_k_entry(tasks)
        elif metric_name == "RespOK":
            entries[metric_name] = _resp_ok_entry(tasks)

    return {
        "total": len(tasks),
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


def build_summary_from_loaded_for_test(
    loaded: Dict[str, Dict[str, Any]], results_dir: Path
) -> Dict[str, Any]:
    by_level = {level: score_level(level, data) for level, data in loaded.items()}
    levels_missing = [level for level in ALL_LEVELS if level not in loaded]
    levels_unscorable = [
        level for level, result in by_level.items()
        if level == "L7" and result.get("score") is None
    ]

    level_scores = [
        result["score"]
        for result in by_level.values()
        if result.get("score") is not None
    ]
    runner_survival_rate = {
        level: data.get("metadata", {}).get("success_rate")
        for level, data in loaded.items()
        if data.get("metadata", {}).get("success_rate") is not None
    }
    runner_survival_rate["note"] = (
        "기존 metadata.success_rate. 정답률이 아니라 'final_response 반환 + step>=1' "
        "생존신호다 (run.py:232-235). 비교용으로 쓰지 말 것."
    )

    track = results_dir.name
    level_values = list(loaded.values())
    return {
        "benchmark": "Ko-AgentBench (deterministic scoring)",
        "model": _model_name(results_dir, level_values),
        "track": track,
        "scoring_version": SCORING_VERSION,
        "native_tool_calling": _native_tool_calling(level_values),
        "agent_score": mean_or_none(level_scores),
        "by_level": by_level,
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

    return build_summary_from_loaded_for_test(loaded, results_dir)


def print_table(summary: Dict[str, Any], skipped_count: int) -> None:
    print(f"{PREFIX} model={summary['model']} track={summary['track']}")
    for level in ALL_LEVELS:
        result = summary["by_level"].get(level)
        if not result:
            continue
        metrics = " ".join(
            f"{name}={_fmt(entry.get('score'))}/{entry.get('status')}"
            for name, entry in result["metrics"].items()
            if entry.get("in_score") or name == "FSM_prefix"
        )
        print(f"{PREFIX} {level} total={result['total']} score={_fmt(result['score'])} {metrics}")
    print(f"{PREFIX} agent_score={_fmt(summary['agent_score'])}")
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
