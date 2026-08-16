"""Pure result-record shaping for GPUStack Ko-AgentBench."""

import json
from typing import Any, Dict, List


def simplify_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """Simplify and flatten a single task result for easier analysis."""
    simplified = {
        "task_id": result.get("task_id", "unknown"),
        "instruction": result.get("instruction", ""),
        "level": result.get("level", 0),
        "category": result.get("category", "unknown"),
        "success": result.get("success", False),
        "execution_time": result.get("execution_time", 0),
        "steps_taken": result.get("steps_taken", 0),
        "error": result.get("error"),
        "expected_tools": result.get("expected_tools", []),
        "golden_action": result.get("golden_action", []),
        "minimum_steps": result.get("minimum_steps"),
        "data_flow": result.get("data_flow", []),
        "error_injection": result.get("error_injection"),
        "fallback_options": result.get("fallback_options", []),
        "resp_schema": result.get("resp_schema", {}),
        "arg_schema": result.get("arg_schema", {}),
        "repetitions": result.get("repetitions", 1),
        "repetition_results": result.get("repetition_results", []),
        "token_usage": result.get("token_usage", {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }),
        "ttft_stats": result.get("ttft_stats", {
            "average": 0,
            "min": 0,
            "max": 0,
            "count": 0
        }),
    }
    if result.get("repetition_records"):
        simplified["repetition_records"] = result.get("repetition_records", [])

    tool_calls = []
    for invocation in result.get("tool_calls", []):
        tool_call = {
            "step": invocation.get("step"),
            "tool_name": invocation.get("tool_name"),
            "arguments": invocation.get("arguments"),
            "success": invocation.get("success"),
            "error": invocation.get("error")
        }

        if invocation.get("success") and invocation.get("result"):
            tool_call["result"] = invocation["result"]

        tool_calls.append(tool_call)

    simplified["tool_calls"] = tool_calls

    if result.get("result") and result["result"].get("final_response"):
        simplified["final_response"] = result["result"]["final_response"]
    else:
        simplified["final_response"] = None

    try:
        conv = (result.get("result") or {}).get("conversation") or []
        total_msgs = len(conv)

        def _format_message(msg):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")

            if role == "tool":
                tcid = msg.get("tool_call_id")
                try:
                    tool_data = json.loads(content) if isinstance(content, str) else content
                    return {
                        "role": role,
                        "tool_call_id": tcid,
                        "content": tool_data
                    }
                except (json.JSONDecodeError, TypeError, ValueError):
                    return {
                        "role": role,
                        "tool_call_id": tcid,
                        "content": content
                    }

            return {"role": role, "content": content}

        simplified["conversation_log"] = {
            "total_messages": total_msgs,
            "messages": [_format_message(m) for m in conv]
        }

    except Exception as e:
        simplified["conversation_log_error"] = str(e)

    return simplified


_REPETITION_DYNAMIC_FIELDS = (
    "success",
    "steps_taken",
    "execution_time",
    "error",
    "tool_calls",
    "final_response",
    "conversation_log",
    "token_usage",
    "ttft_stats",
)


def repetition_record(result: Dict[str, Any], rep_index: int, seed=None) -> Dict[str, Any]:
    simplified = simplify_result(result)
    record = {"rep_index": rep_index}
    for key in _REPETITION_DYNAMIC_FIELDS:
        if key in simplified:
            record[key] = simplified[key]
    if seed is not None:
        record["seed"] = seed
    return record


def failure_repetition_record(error: str, rep_index: int, seed=None) -> Dict[str, Any]:
    record = {
        "rep_index": rep_index,
        "success": False,
        "steps_taken": 0,
        "execution_time": 0,
        "error": error,
        "tool_calls": [],
        "final_response": None,
        "conversation_log": {"total_messages": 0, "messages": []},
        "token_usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
        "ttft_stats": {
            "average": 0,
            "min": 0,
            "max": 0,
            "count": 0,
        },
    }
    if seed is not None:
        record["seed"] = seed
    return record


def failed_task_record(
    task: Dict[str, Any],
    error: str,
    repetitions: int,
    repetition_results: List[bool],
    repetition_records: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "task_id": task.get('id', 'unknown'),
        "instruction": task.get('description', ''),
        "level": task.get('level', 0),
        "category": task.get('category', 'unknown'),
        "expected_tools": task.get('available_tools', []),
        "golden_action": task.get('golden_action', []),
        "minimum_steps": task.get('minimum_steps'),
        "data_flow": task.get('data_flow', []),
        "repetitions": repetitions,
        "repetition_results": repetition_results + [False] * (repetitions - len(repetition_results)),
        **({"repetition_records": repetition_records} if repetitions > 1 else {}),
        "success": False,
        "error": error,
        "execution_time": 0,
        "steps_taken": 0,
        "tool_invocations": [],
        "tool_calls": []
    }


def build_detailed_results_log(
    results: List[Dict[str, Any]],
    model_name: str,
    level_name: str,
    metadata_timestamp: str,
    native_tool_calling: bool = False,
) -> Dict[str, Any]:
    simplified_results = [simplify_result(r) for r in results]

    total_tasks = len(simplified_results)
    successful_tasks = sum(1 for r in simplified_results if r.get('success', False))
    total_time = sum(r.get('execution_time', 0) for r in simplified_results)
    total_steps = sum(r.get('steps_taken', 0) for r in simplified_results)
    total_tool_calls = sum(len(r.get('tool_calls', [])) for r in simplified_results)

    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_tokens = 0
    all_ttft_values = []

    for result in simplified_results:
        token_usage = result.get('token_usage', {})
        total_prompt_tokens += token_usage.get('prompt_tokens', 0)
        total_completion_tokens += token_usage.get('completion_tokens', 0)
        total_tokens += token_usage.get('total_tokens', 0)

        ttft_stats = result.get('ttft_stats', {})
        avg_ttft = ttft_stats.get('average', 0)
        if avg_ttft > 0:
            all_ttft_values.append(avg_ttft)

    average_tps = total_tokens / total_time if total_time > 0 else 0

    average_ttft = sum(all_ttft_values) / len(all_ttft_values) if all_ttft_values else 0
    min_ttft = min(all_ttft_values) if all_ttft_values else 0
    max_ttft = max(all_ttft_values) if all_ttft_values else 0

    tool_usage_stats = {}
    for result in simplified_results:
        for tool_call in result.get('tool_calls', []):
            tool_name = tool_call.get('tool_name', 'unknown')
            if tool_name not in tool_usage_stats:
                tool_usage_stats[tool_name] = {
                    'count': 0,
                    'success': 0,
                    'failure': 0
                }
            tool_usage_stats[tool_name]['count'] += 1
            if tool_call.get('success', False):
                tool_usage_stats[tool_name]['success'] += 1
            else:
                tool_usage_stats[tool_name]['failure'] += 1

    return {
        "metadata": {
            "timestamp": metadata_timestamp,
            "model": model_name,
            "level": level_name,
            "native_tool_calling": native_tool_calling,
            "total_tasks": total_tasks,
            "successful_tasks": successful_tasks,
            "failed_tasks": total_tasks - successful_tasks,
            "success_rate": round(successful_tasks / total_tasks * 100, 2) if total_tasks > 0 else 0,
            "total_execution_time": round(total_time, 2),
            "average_execution_time": round(total_time / total_tasks, 2) if total_tasks > 0 else 0,
            "total_steps": total_steps,
            "average_steps": round(total_steps / total_tasks, 2) if total_tasks > 0 else 0,
            "total_tool_calls": total_tool_calls,
            "average_tool_calls": round(total_tool_calls / total_tasks, 2) if total_tasks > 0 else 0,
            "total_tokens": total_tokens,
            "average_tokens_per_task": round(total_tokens / total_tasks, 2) if total_tasks > 0 else 0,
            "average_prompt_tokens": round(total_prompt_tokens / total_tasks, 2) if total_tasks > 0 else 0,
            "average_completion_tokens": round(total_completion_tokens / total_tasks, 2) if total_tasks > 0 else 0,
            "average_tps": round(average_tps, 2),
            "ttft": {
                "average": round(average_ttft, 4),
                "min": round(min_ttft, 4),
                "max": round(max_ttft, 4),
                "unit": "seconds"
            },
        },
        "tool_usage_statistics": tool_usage_stats,
        "results": simplified_results
    }
