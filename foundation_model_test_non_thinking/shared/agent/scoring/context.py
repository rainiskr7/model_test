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


def task_to_schema_and_logs(task_result: Dict[str, Any]):
    """Return task_schema/logs using the same keys as evaluate_model_run.py."""
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


def build_eval_context(task_result: Dict[str, Any]):
    metrics = load_metrics_module()
    task_schema, logs = task_to_schema_and_logs(task_result)
    return metrics.EvalContext(task_schema=task_schema, logs=logs)
