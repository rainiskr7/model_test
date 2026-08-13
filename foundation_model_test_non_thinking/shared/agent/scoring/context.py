"""Build Ko-AgentBench EvalContext objects from saved task results."""

from typing import Any, Dict

try:
    from .bench_path import ensure_bench_path
except ImportError:  # direct file loading in tests
    from bench_path import ensure_bench_path


def load_metrics_module():
    ensure_bench_path()
    from bench.runner import metrics

    return metrics


class BenchDriftError(RuntimeError):
    """Raised when saved result facts disagree with the bench task source."""


_BENCH_STATIC_FIELDS = (
    "golden_fields",
    "minimum_calls",
    "freshness_threshold",
    "conversation_tracking",
    "long_term_tests",
    "minimum_sources",
    "essential_tools",
)


def _has_value(data: Dict[str, Any], key: str) -> bool:
    return key in data and data.get(key) is not None


def _is_level_7(task_schema: Dict[str, Any], task_result: Dict[str, Any], bench_task=None) -> bool:
    value = (
        task_schema.get("task_level")
        if task_schema.get("task_level") is not None
        else task_result.get("task_level")
    )
    if value is None and bench_task:
        value = bench_task.get("task_level") or bench_task.get("level")
    return str(value).upper() in {"7", "L7"}


def _synthesize_l7_golden_action(task_schema: Dict[str, Any]) -> None:
    if task_schema.get("golden_action"):
        return

    tracking = task_schema.get("conversation_tracking") or {}
    eval_context = tracking.get("evaluation_context") or {}
    context_tests = eval_context.get("context_tests") or []
    expected_actions = [
        test["expected_action"]
        for test in context_tests
        if isinstance(test, dict) and test.get("expected_action")
    ]
    if expected_actions:
        task_schema["golden_action"] = expected_actions
        task_schema["_golden_action_synthesized"] = True


def task_to_schema_and_logs(task_result: Dict[str, Any], bench_task: Dict[str, Any] = None):
    """Return task_schema/logs using the same keys as evaluate_model_run.py."""
    if bench_task is not None:
        result_golden = task_result.get("golden_action")
        bench_golden = bench_task.get("golden_action")
        if result_golden is not None and bench_golden is not None and result_golden != bench_golden:
            task_id = task_result.get("task_id") or bench_task.get("task_id")
            raise BenchDriftError(f"golden_action drift for task_id={task_id}")

    task_schema = {
        "task_id": task_result.get("task_id"),
        "instruction": task_result.get("instruction"),
        "task_level": task_result.get("level"),
        "task_category": task_result.get("category"),
        "golden_action": task_result.get("golden_action", []),
        "minimum_steps": task_result.get("minimum_steps"),
        "data_flow": task_result.get("data_flow", []),
        "available_tools": task_result.get("expected_tools", []),
        "error_injection": task_result.get("error_injection"),
        "fallback_options": task_result.get("fallback_options", []),
        "resp_schema": task_result.get("resp_schema"),
        "arg_schema": task_result.get("arg_schema"),
        "repetitions": task_result.get("repetitions", 1),
    }

    if bench_task is not None:
        for key in _BENCH_STATIC_FIELDS:
            if _has_value(task_result, key):
                task_schema[key] = task_result.get(key)
            elif key in bench_task:
                task_schema[key] = bench_task.get(key)

        if not task_schema.get("golden_action") and bench_task.get("golden_action") is not None:
            task_schema["golden_action"] = bench_task.get("golden_action")

        if _is_level_7(task_schema, task_result, bench_task):
            _synthesize_l7_golden_action(task_schema)

    logs = {
        "success": task_result.get("success", False),
        "tool_invocations": task_result.get("tool_calls", []),
        "tool_calls": task_result.get("tool_calls", []),
        "actual_output": task_result.get("final_response", ""),
        "final_response": task_result.get("final_response", ""),
        "conversation_log": task_result.get("conversation_log", {}),
        "repetition_results": task_result.get("repetition_results", []),
    }
    return task_schema, logs


def build_eval_context(task_result: Dict[str, Any], bench_task: Dict[str, Any] = None):
    metrics = load_metrics_module()
    task_schema, logs = task_to_schema_and_logs(task_result, bench_task)
    return metrics.EvalContext(task_schema=task_schema, logs=logs)
