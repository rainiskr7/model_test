"""Aggregation policy for deterministic Ko-AgentBench agent scoring."""

import math
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List

if __package__:
    from . import SCORING_VERSION, SCORING_VERSION_V3, SCORING_VERSION_V4
    from .cache_diagnostics import CACHE_MISS_RE, build_cache_diagnostics
    from .context import build_eval_context
    from .level_spec import (
        COMMON_RECORD_ONLY,
        JUDGE_METRICS,
        LEVEL_SPECS,
        LEVEL_SPECS_V3,
        MetricSpec,
        level_score,
        mean_or_none,
        vendored_metric,
    )
    from .task_data import prepare_v3_loaded
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from __init__ import SCORING_VERSION, SCORING_VERSION_V3, SCORING_VERSION_V4
    from cache_diagnostics import CACHE_MISS_RE, build_cache_diagnostics
    from context import build_eval_context
    from level_spec import (
        COMMON_RECORD_ONLY,
        JUDGE_METRICS,
        LEVEL_SPECS,
        LEVEL_SPECS_V3,
        MetricSpec,
        level_score,
        mean_or_none,
        vendored_metric,
    )
    from task_data import prepare_v3_loaded


ALL_LEVELS = tuple(f"L{i}" for i in range(1, 8))
SCORABLE_LEVELS = ("L1", "L2", "L3", "L4", "L5", "L6")

# A scoring version's denominator is a pinned constant. It must never be chosen
# from the data being scored, so this is deliberately not a runtime
# auto-exclusion predicate. V4 excludes a level only when all four conditions
# were established on the frozen benchmark evidence: (1) every in-scope metric
# derives success/count from tool-response outcomes rather than call shape;
# (2) a material share of those outcome labels on the pinned fixture set are
# cache misses; (3) the level score is not separable from that miss process; and
# (4) the misses are not repairable under the fixture freeze.
#
# L4 satisfies all four: Coverage and SourceEPR both count distinct tools whose
# responses succeeded over distinct required tools, cache misses become
# success=False, the score therefore absorbs the misses, and 0/177 measured
# misses are repairable under the frozen key-matching rules. L3 fails (1), but
# its misses still propagate through retry-inflated call sequences and strongly
# depress the level; removing L3 shifts the six-model headline by at most 0.019
# and preserves order. L5 remains included because its two runner-imposed 0.5
# metric ceilings compress scale without removing signal: rescaling preserves
# the six-model order, while dropping L5 changes it. L6 v3 reads whether a
# refetch happened, not a response payload.
V4_HEADLINE_LEVELS = ("L1", "L2", "L3", "L5", "L6")
V4_EXCLUDED_LEVELS = ("L4",)
L4_FIXTURE_COVERAGE_NOTICE = (
    "L4 Coverage/SourceEPR treat a cache miss as success=False; L4 is excluded "
    "from v4 because those labels measure fixture coverage, not capability."
)
L5_METRIC_CEILINGS = {
    "FallbackSR": 1.0,
    "AdaptiveRoutingScore": 0.5,
    "EPR_CVR": 0.5,
}
L5_LEVEL_CEILING = sum(L5_METRIC_CEILINGS.values()) / len(L5_METRIC_CEILINGS)
L5_CEILING_NOTICE = (
    "AdaptiveRoutingScore and EPR_CVR are capped at 0.5 for schema-respecting "
    "models: the runner withholds fallback tools until a reset second pass "
    "(forcing a step gap) and injects one mandatory failed call."
)


def _tasks(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    tasks = data.get("results")
    if isinstance(tasks, list):
        return tasks
    tasks = data.get("tasks")
    if isinstance(tasks, list):
        return tasks
    return []


def _call_tool(call: Dict[str, Any]):
    return call.get("tool_name") or call.get("tool")


def _call_arguments(call: Dict[str, Any]):
    arguments = call.get("arguments")
    if isinstance(arguments, dict):
        return arguments
    arguments = call.get("args")
    return arguments if isinstance(arguments, dict) else {}


def _diagnostic_failures(count: int, first_error: Any) -> Dict[str, Any]:
    entry = {"count": count}
    if first_error is not None:
        entry["error"] = f"{type(first_error).__name__}: {first_error}"
    return entry


def _build_l3_retry_inflation(level_data: Dict[str, Any]) -> Dict[str, Any]:
    class_names = (
        "no_tool_calls_emitted",
        "no_cache_miss",
        "cache_miss_only_at_final_call",
        "cache_miss_before_final_call",
    )
    classes = {
        name: {
            "tasks": 0,
            "calls_emitted": 0,
            "golden_action_calls": 0,
            "inflation_ratio": None,
        }
        for name in class_names
    }
    after_non_final_miss = {
        "misses_with_following_call": 0,
        "same_tool_identical_arguments": 0,
        "same_tool_different_arguments": 0,
        "different_tool": 0,
    }
    context_failure_count = 0
    first_context_error = None

    for task in _tasks(level_data):
        if not isinstance(task, dict):
            continue
        try:
            build_eval_context(task)
        except Exception as exc:
            context_failure_count += 1
            if first_context_error is None:
                first_context_error = exc
        # L3 수치는 저장된 call만 읽으므로 context 실패와 무관하게 기존 분류를 유지한다.
        calls = task.get("tool_calls")
        calls = calls if isinstance(calls, list) else []
        golden_action = task.get("golden_action")
        if isinstance(golden_action, dict):
            golden_action = [golden_action]
        elif not isinstance(golden_action, list):
            golden_action = []
        miss_indexes = [
            index
            for index, call in enumerate(calls)
            if isinstance(call, dict)
            and CACHE_MISS_RE.search(str(call.get("error") or ""))
        ]
        if not calls:
            class_name = "no_tool_calls_emitted"
        elif not miss_indexes:
            class_name = "no_cache_miss"
        elif miss_indexes == [len(calls) - 1]:
            class_name = "cache_miss_only_at_final_call"
        else:
            class_name = "cache_miss_before_final_call"

        entry = classes[class_name]
        entry["tasks"] += 1
        entry["calls_emitted"] += len(calls)
        entry["golden_action_calls"] += len(golden_action)

        for index in miss_indexes:
            if index >= len(calls) - 1:
                continue
            current = calls[index]
            following = calls[index + 1]
            if not isinstance(current, dict) or not isinstance(following, dict):
                after_non_final_miss["different_tool"] += 1
            elif _call_tool(current) != _call_tool(following):
                after_non_final_miss["different_tool"] += 1
            elif _call_arguments(current) == _call_arguments(following):
                after_non_final_miss["same_tool_identical_arguments"] += 1
            else:
                after_non_final_miss["same_tool_different_arguments"] += 1
            after_non_final_miss["misses_with_following_call"] += 1

    for name, entry in classes.items():
        if name == "no_tool_calls_emitted":
            continue
        golden_calls = entry["golden_action_calls"]
        if golden_calls:
            entry["inflation_ratio"] = entry["calls_emitted"] / golden_calls

    return {
        "classes": classes,
        "after_non_final_miss": after_non_final_miss,
        "context_construction_failures": _diagnostic_failures(
            context_failure_count, first_context_error
        ),
    }


def _build_l5_ceiling(level_data: Dict[str, Any]) -> Dict[str, Any]:
    observed = {name: [] for name in L5_METRIC_CEILINGS}
    producer_failure_counts = {name: 0 for name in L5_METRIC_CEILINGS}
    first_producer_errors = {name: None for name in L5_METRIC_CEILINGS}
    context_failure_count = 0
    first_context_error = None
    specs = {
        spec.name: spec
        for spec in LEVEL_SPECS_V3["L5"]
        if spec.in_score and spec.name in observed
    }
    for task in _tasks(level_data):
        if not isinstance(task, dict):
            continue
        try:
            ctx = build_eval_context(task)
        except Exception as exc:
            context_failure_count += 1
            if first_context_error is None:
                first_context_error = exc
            continue
        for name, spec in specs.items():
            try:
                value = spec.producer(ctx)
                numeric = float(value) if value is not None else None
                if (
                    numeric is not None
                    and math.isfinite(numeric)
                    and 0.0 <= numeric <= 1.0
                ):
                    observed[name].append(numeric)
            except Exception as exc:
                producer_failure_counts[name] += 1
                if first_producer_errors[name] is None:
                    first_producer_errors[name] = exc
                continue

    return {
        "metrics": {
            name: {
                "observed_max": max(observed[name]) if observed[name] else None,
                "structural_ceiling": ceiling,
                "producer_failures": _diagnostic_failures(
                    producer_failure_counts[name], first_producer_errors[name]
                ),
            }
            for name, ceiling in L5_METRIC_CEILINGS.items()
        },
        "context_construction_failures": _diagnostic_failures(
            context_failure_count, first_context_error
        ),
        "level_ceiling": L5_LEVEL_CEILING,
        "statement": L5_CEILING_NOTICE,
    }


def _average_metric(tasks: List[Dict[str, Any]], spec: MetricSpec) -> Dict[str, Any]:
    scores = []
    errors = []
    contract_errors = []
    task_spread = {"n_perfect": 0, "n_zero": 0, "n_partial": 0}
    diagnostics: Dict[str, int] = (
        {
            "fields_required": 0,
            "fields_checked": 0,
            "fields_excluded_long_text": 0,
            "fields_unresolved": 0,
        }
        if spec.diagnostic_producer
        else {}
    )
    for task in tasks:
        try:
            ctx = build_eval_context(task)
            score = spec.producer(ctx)
            task_diagnostics = (
                spec.diagnostic_producer(ctx) if spec.diagnostic_producer else {}
            )
            if score is not None:
                numeric_score = float(score)
                if not math.isfinite(numeric_score) or not 0.0 <= numeric_score <= 1.0:
                    contract_errors.append(
                        {
                            "metric": spec.name,
                            "task_id": task.get("task_id") or "unknown",
                            "raw_value": repr(score),
                            "violation": (
                                "non_finite"
                                if not math.isfinite(numeric_score)
                                else "out_of_range"
                            ),
                        }
                    )
                else:
                    scores.append(numeric_score)
                    if numeric_score == 1.0:
                        task_spread["n_perfect"] += 1
                    elif numeric_score == 0.0:
                        task_spread["n_zero"] += 1
                    else:
                        task_spread["n_partial"] += 1
            for name, count in task_diagnostics.items():
                diagnostics[name] = diagnostics.get(name, 0) + int(count)
        except Exception as exc:
            errors.append(exc)

    if contract_errors:
        status = "contract_error"
    elif errors:
        status = "partial" if scores else "error"
    else:
        status = "ok" if scores else "not_applicable"

    entry = {
        "score": None if contract_errors else mean_or_none(scores),
        "status": status,
        "in_score": spec.in_score,
        "n_tasks": len(tasks),
        "n_scored": len(scores),
        "n_errors": len(errors),
        "n_contract_errors": len(contract_errors),
        "task_spread": task_spread,
    }
    entry.update(diagnostics)
    if errors:
        exc = errors[0]
        entry["error"] = f"{type(exc).__name__}: {exc}"
    if contract_errors:
        entry["contract_errors"] = contract_errors
    return entry


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
    return _average_metric(tasks, MetricSpec("pass@k", vendored_metric("pass@k"), False))


def _resp_ok_entry(tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
    if all((task.get("resp_schema") or {}).get("type") == "string" for task in tasks):
        return {
            "score": None,
            "status": "not_applicable",
            "in_score": False,
            "reason": "resp_schema.type == string",
        }
    return _average_metric(tasks, MetricSpec("RespOK", vendored_metric("RespOK"), False))


def _unscorable_reason(
    level: str,
    total: int,
    entries: Dict[str, Dict[str, Any]],
    level_specs,
) -> str:
    if not level_specs[level]:
        return "no_deterministic_metric"
    if total == 0:
        return "no_tasks"
    if any(
        entry.get("status") == "contract_error" for entry in entries.values()
    ):
        return "metric_contract_error"
    if any(
        entry.get("in_score") and entry.get("status") == "error"
        for entry in entries.values()
    ):
        return "metric_error"
    return "all_not_applicable"


def _score_level_with_specs(level: str, data: Dict[str, Any], level_specs) -> Dict[str, Any]:
    tasks = _tasks(data)
    entries: Dict[str, Dict[str, Any]] = {}

    for spec in level_specs[level]:
        entries[spec.name] = _average_metric(tasks, spec)

    for metric_name in JUDGE_METRICS:
        entries[metric_name] = _judge_entry()

    for metric_name in COMMON_RECORD_ONLY:
        if metric_name == "pass@k":
            entries[metric_name] = _pass_at_k_entry(tasks)
        elif metric_name == "RespOK":
            entries[metric_name] = _resp_ok_entry(tasks)

    fatal_metric_error = any(
        entry.get("status") == "contract_error"
        or (entry.get("in_score") and entry.get("status") == "error")
        for entry in entries.values()
    )
    score = None if fatal_metric_error else level_score(entries)
    result = {
        "total": len(tasks),
        "score": score,
        "applied_metrics": sum(
            entry.get("in_score")
            and entry.get("status") in {"ok", "partial"}
            for entry in entries.values()
        ),
        "metrics": entries,
    }
    if score is None:
        result["unscorable_reason"] = _unscorable_reason(
            level, len(tasks), entries, level_specs
        )
    return result


def score_level(level: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Score under the frozen v2 contract (kept as the compatibility API)."""
    return _score_level_with_specs(level, data, LEVEL_SPECS)


def _build_v4_block(
    v3_by_level: Dict[str, Dict[str, Any]],
    levels_missing: List[str],
    task_data_provenance: Dict[str, Any],
) -> Dict[str, Any]:
    """Build the pinned five-level v4 headline from the v3 level matrix."""
    levels_unscorable = [
        level for level, result in v3_by_level.items() if result.get("score") is None
    ]
    scored_levels = sum(
        1
        for level in V4_HEADLINE_LEVELS
        if level in v3_by_level and v3_by_level[level].get("score") is not None
    )
    required_levels = len(V4_HEADLINE_LEVELS)
    complete = scored_levels == required_levels
    agent_score = (
        mean_or_none([v3_by_level[level]["score"] for level in V4_HEADLINE_LEVELS])
        if complete
        else None
    )
    return {
        "scoring_version": SCORING_VERSION_V4,
        "agent_score": agent_score,
        "scored_levels": scored_levels,
        "required_levels": required_levels,
        "agent_score_status": "complete" if complete else "incomplete",
        "headline_levels": list(V4_HEADLINE_LEVELS),
        "excluded_levels": list(V4_EXCLUDED_LEVELS),
        "by_level": v3_by_level,
        "levels_missing": levels_missing,
        "levels_unscorable": levels_unscorable,
        "task_data": task_data_provenance,
    }


def _native_tool_calling(level_data: Iterable[Dict[str, Any]]):
    for data in level_data:
        metadata = data.get("metadata") or {}
        if "native_tool_calling" in metadata:
            return metadata.get("native_tool_calling")
    # 이 필드가 추가되기 전 결과는 text parser 기반(non-native) 런이었다.
    # 오래된 raw 결과를 재채점해도 현재 summary 계약(boolean)을 만족시킨다.
    return False


def safe_model_name(model: str) -> str:
    return model.replace("/", "_").replace("-", "_").replace(":", "_")


def _model_name(results_dir: Path, level_data: Iterable[Dict[str, Any]]) -> str:
    for data in level_data:
        metadata = data.get("metadata") or {}
        if metadata.get("model"):
            return safe_model_name(str(metadata["model"]))
    try:
        return results_dir.parents[2].name
    except IndexError:
        return ""


def build_summary_from_loaded(
    loaded: Dict[str, Dict[str, Any]], results_dir: Path
) -> Dict[str, Any]:
    # The top-level contract is the published, frozen v2 summary. Keep this
    # construction and all existing field meanings intact.
    by_level = {level: score_level(level, data) for level, data in loaded.items()}
    levels_missing = [level for level in ALL_LEVELS if level not in loaded]
    levels_unscorable = [
        level for level, result in by_level.items() if result.get("score") is None
    ]

    scored_levels = sum(
        1
        for level in SCORABLE_LEVELS
        if level in by_level and by_level[level].get("score") is not None
    )
    required_levels = len(SCORABLE_LEVELS)
    complete = scored_levels == required_levels
    # Equal level weighting is a frozen score definition. Do not infer new weights
    # from a saturated cohort (including trivial L2); that requires a version bump.
    # L7 deterministic metrics are record-only and do not contribute to agent_score.
    agent_score = (
        mean_or_none([by_level[level]["score"] for level in SCORABLE_LEVELS])
        if complete
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

    track = results_dir.name
    level_values = list(loaded.values())
    summary = {
        "benchmark": "Ko-AgentBench (deterministic scoring)",
        "model": _model_name(results_dir, level_values),
        "track": track,
        "scoring_version": SCORING_VERSION,
        "native_tool_calling": _native_tool_calling(level_values),
        "agent_score": agent_score,
        "scored_levels": scored_levels,
        "required_levels": required_levels,
        "agent_score_status": "complete" if complete else "incomplete",
        "by_level": by_level,
        "runner_survival_rate": runner_survival_rate,
        "levels_missing": levels_missing,
        "levels_unscorable": levels_unscorable,
    }

    v3_loaded, task_data_provenance = prepare_v3_loaded(loaded)
    v3_by_level = {
        level: _score_level_with_specs(level, data, LEVEL_SPECS_V3)
        for level, data in v3_loaded.items()
    }
    v3_levels_unscorable = [
        level for level, result in v3_by_level.items() if result.get("score") is None
    ]
    v3_scored_levels = sum(
        1
        for level in SCORABLE_LEVELS
        if level in v3_by_level and v3_by_level[level].get("score") is not None
    )
    v3_complete = v3_scored_levels == required_levels
    v3_agent_score = (
        mean_or_none([v3_by_level[level]["score"] for level in SCORABLE_LEVELS])
        if v3_complete
        else None
    )
    summary["scoring_v3"] = {
        "scoring_version": SCORING_VERSION_V3,
        "agent_score": v3_agent_score,
        "scored_levels": v3_scored_levels,
        "required_levels": required_levels,
        "agent_score_status": "complete" if v3_complete else "incomplete",
        "by_level": v3_by_level,
        "levels_missing": levels_missing,
        "levels_unscorable": v3_levels_unscorable,
        "task_data": task_data_provenance,
    }
    summary["scoring_v4"] = _build_v4_block(
        v3_by_level, levels_missing, task_data_provenance
    )
    summary["headline_denominators"] = {
        SCORING_VERSION: list(SCORABLE_LEVELS),
        SCORING_VERSION_V3: list(SCORABLE_LEVELS),
        SCORING_VERSION_V4: list(V4_HEADLINE_LEVELS),
    }
    # Additive and score-neutral: diagnostics only observe saved tasks/calls and
    # fixed metric definitions after all scoring contracts have been computed.
    summary["cache_miss_diagnostics"] = build_cache_diagnostics(
        loaded, results_dir
    )
    l4_diagnostic = (
        summary["cache_miss_diagnostics"].get("by_level", {}).get("L4", {})
    )
    summary["l4_fixture_coverage"] = {
        "score": (v3_by_level.get("L4") or {}).get("score"),
        "cache_misses": l4_diagnostic.get("cache_misses", 0),
        "total_calls": l4_diagnostic.get("total_calls", 0),
        "miss_rate": l4_diagnostic.get("miss_rate", 0.0),
        "miss_counts": l4_diagnostic.get("miss_counts", {}),
        "statement": L4_FIXTURE_COVERAGE_NOTICE,
    }
    summary["l3_retry_inflation"] = _build_l3_retry_inflation(
        loaded.get("L3", {})
    )
    summary["l5_ceiling"] = _build_l5_ceiling(loaded.get("L5", {}))
    return summary
