"""Data-health diagnostics for deterministic agent scoring."""

import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

if __package__:
    from . import extra_metrics
    from .context import build_eval_context, load_vendored_metric
    from .l6_context import l6_golden_field_diagnostics
    from .result_shape import has_repetition_records as _has_repetition_records
    from .task_source import load_bench_tasks
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import extra_metrics
    from context import build_eval_context, load_vendored_metric
    from l6_context import l6_golden_field_diagnostics
    from result_shape import has_repetition_records as _has_repetition_records
    from task_source import load_bench_tasks


def _tool_call_count(task: Dict[str, Any]) -> int:
    # 반복 기록 인정 규칙은 _has_repetition_records 와 동일하게 둔다 (빈 리스트는 부모로 폴백).
    # 어긋나면 repetition_records: [] 인 태스크가 부모 tool_calls 로 채점되면서
    # data_health 에는 0 으로 잡혀 잘못된 경고가 뜬다.
    if _has_repetition_records(task):
        total = 0
        for record in task["repetition_records"]:
            if not isinstance(record, dict):
                continue
            tool_calls = record.get("tool_calls")
            if isinstance(tool_calls, list):
                total += len(tool_calls)
        return total

    tool_calls = task.get("tool_calls")
    return len(tool_calls) if isinstance(tool_calls, list) else 0


def _steps_taken_is_zero(record: Dict[str, Any]) -> bool:
    steps_taken = record.get("steps_taken")
    return not (isinstance(steps_taken, int) and not isinstance(steps_taken, bool) and steps_taken > 0)


def _zero_step_task(task: Dict[str, Any]) -> bool:
    if not _steps_taken_is_zero(task):
        return False
    if _has_repetition_records(task):
        return all(
            not isinstance(record, dict) or _steps_taken_is_zero(record)
            for record in task["repetition_records"]
        )
    return True


def _final_response_is_empty(record: Dict[str, Any]) -> bool:
    if "final_response" not in record or record.get("final_response") is None:
        return True
    return str(record.get("final_response")).strip() == ""


def _empty_response_task(task: Dict[str, Any]) -> bool:
    if _has_repetition_records(task):
        return all(
            not isinstance(record, dict) or _final_response_is_empty(record)
            for record in task["repetition_records"]
        )
    return _final_response_is_empty(task)


def _vendored(name: str):
    def _evaluate(ctx):
        return load_vendored_metric(name).evaluate(ctx).score

    return _evaluate


def _l6_data_health(tasks: List[Dict[str, Any]], bench_tasks: Optional[Dict[str, dict]]) -> Dict[str, int]:
    if bench_tasks is None and tasks:
        try:
            bench_tasks = load_bench_tasks("L6")
        except Exception:
            bench_tasks = None

    seeded_echo_tasks = 0
    unresolved_field_tasks = 0
    scored_tasks = 0
    fallback_resolved_fields = 0
    for task in tasks:
        try:
            bench_task = None
            if bench_tasks is not None:
                bench_task = bench_tasks.get(str(task.get("task_id")))
            ctx = build_eval_context(task, bench_task)
            diagnostics = l6_golden_field_diagnostics(ctx)
        except Exception:
            continue
        if diagnostics.get("seeded_echo"):
            seeded_echo_tasks += 1
        if diagnostics.get("unresolved_fields", 0) > 0:
            unresolved_field_tasks += 1
        if diagnostics.get("scorable_values"):
            scored_tasks += 1
        fallback_resolved_fields += int(diagnostics.get("fallback_fields", 0))

    return {
        "seeded_echo_tasks": seeded_echo_tasks,
        "unresolved_field_tasks": unresolved_field_tasks,
        "scored_tasks": scored_tasks,
        "fallback_resolved_fields": fallback_resolved_fields,
    }


def _l3_data_health(tasks: List[Dict[str, Any]], bench_tasks: Optional[Dict[str, dict]]) -> Dict[str, int]:
    if bench_tasks is None and tasks:
        try:
            bench_tasks = load_bench_tasks("L3")
        except Exception:
            bench_tasks = None

    prefix_only_tasks = 0
    fsm_strict = _vendored("FSM")
    for task in tasks:
        try:
            bench_task = None
            if bench_tasks is not None:
                bench_task = bench_tasks.get(str(task.get("task_id")))
            ctx = build_eval_context(task, bench_task)
            prefix_score = extra_metrics.fsm_prefix(ctx)
            strict_score = fsm_strict(ctx)
        except Exception:
            continue
        if prefix_score == 1.0 and strict_score == 0.0:
            prefix_only_tasks += 1

    return {
        "prefix_only_tasks": prefix_only_tasks,
    }

def build_data_health(
    loaded: Dict[str, Dict[str, Any]],
    bench_task_maps: Dict[str, Dict[str, dict]],
    tasks_of: Callable[[Dict[str, Any]], List[Dict[str, Any]]],
) -> Dict[str, Any]:
    data_health_by_level = {}
    total_tasks = 0
    tasks_with_tool_calls = 0
    total_tool_calls = 0
    total_zero_step_tasks = 0
    total_empty_response_tasks = 0
    for level, data in loaded.items():
        tasks = tasks_of(data)
        level_tool_calls = sum(_tool_call_count(task) for task in tasks)
        level_tasks_with_tool_calls = sum(1 for task in tasks if _tool_call_count(task) > 0)
        level_zero_step_tasks = sum(1 for task in tasks if _zero_step_task(task))
        level_empty_response_tasks = sum(1 for task in tasks if _empty_response_task(task))
        data_health_by_level[level] = {
            "tasks": len(tasks),
            "tasks_with_tool_calls": level_tasks_with_tool_calls,
            "tool_calls": level_tool_calls,
            "zero_step_tasks": level_zero_step_tasks,
            "empty_response_tasks": level_empty_response_tasks,
        }
        if level == "L6":
            data_health_by_level[level].update(
                _l6_data_health(tasks, bench_task_maps.get("L6"))
            )
        elif level == "L3":
            data_health_by_level[level].update(
                _l3_data_health(tasks, bench_task_maps.get("L3"))
            )
        total_tasks += len(tasks)
        tasks_with_tool_calls += level_tasks_with_tool_calls
        total_tool_calls += level_tool_calls
        total_zero_step_tasks += level_zero_step_tasks
        total_empty_response_tasks += level_empty_response_tasks

    data_health = {
        "total_tasks": total_tasks,
        "tasks_with_tool_calls": tasks_with_tool_calls,
        "total_tool_calls": total_tool_calls,
        "no_tool_calls_recorded": total_tasks > 0 and total_tool_calls == 0,
        "zero_step_tasks": total_zero_step_tasks,
        "empty_response_tasks": total_empty_response_tasks,
        "by_level": data_health_by_level,
    }
    if data_health["no_tool_calls_recorded"]:
        data_health["warning"] = (
            "저장된 결과에 tool_call 기록이 하나도 없다. 모든 결정론 지표가 구조적으로 0 이 되므로 "
            "이 점수는 모델 성능이 아니라 러너/파서 산출물 문제일 수 있다 (tool_call 파서 수정 이전 런일 가능성)."
        )
    return data_health
