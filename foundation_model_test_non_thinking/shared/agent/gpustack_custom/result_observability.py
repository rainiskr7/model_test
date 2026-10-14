"""Dependency-free agent result formatting, metadata and JSON persistence."""

import json

from typing import Any, Dict, Iterable, Mapping


def _number(value: Any) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    return 0


def completion_latency_from_task(result: Mapping[str, Any]) -> Dict[str, Any]:
    """Translate the vendored runner's non-streaming timing into a truthful name."""
    stats = result.get("completion_latency")
    if not isinstance(stats, Mapping):
        # Ko-AgentBench currently calls full-response latency ``ttft_stats``.
        stats = result.get("ttft_stats")
    if not isinstance(stats, Mapping):
        stats = {}
    return {
        "average": _number(stats.get("average")),
        "min": _number(stats.get("min")),
        "max": _number(stats.get("max")),
        "count": int(_number(stats.get("count"))),
        "unit": "seconds",
    }


def finish_reason_fields(result: Mapping[str, Any]) -> Dict[str, Any]:
    """Extract finish reasons from model responses retained in task steps."""
    task_result = result.get("result")
    steps = task_result.get("steps", []) if isinstance(task_result, Mapping) else []
    reasons = []
    for step in steps if isinstance(steps, list) else []:
        if not isinstance(step, Mapping):
            continue
        response = step.get("llm_response")
        if isinstance(response, Mapping):
            reasons.append(response.get("finish_reason"))
    return {
        "last_finish_reason": reasons[-1] if reasons else None,
        "length_finish_reason_count": int(sum(reason == "length" for reason in reasons)),
    }


def build_observability_metadata(
    simplified_results: Iterable[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Build level-wide latency and truncation metadata for newly saved results."""
    results = list(simplified_results)
    average_values = []
    for result in results:
        latency = result.get("completion_latency")
        if isinstance(latency, Mapping):
            average = _number(latency.get("average"))
            if average > 0:
                average_values.append(average)

    average = sum(average_values) / len(average_values) if average_values else 0
    return {
        "completion_latency": {
            "average": round(average, 4),
            "min": round(min(average_values), 4) if average_values else 0,
            "max": round(max(average_values), 4) if average_values else 0,
            "unit": "seconds",
        },
        "tasks_with_length_finish_reason": int(
            sum(int(_number(result.get("length_finish_reason_count"))) > 0 for result in results)
        ),
    }


def read_completion_latency(summary: Mapping[str, Any]) -> Dict[str, Any]:
    """Read new summaries and legacy summaries that used the misleading ``ttft`` key."""
    metadata = summary.get("metadata", summary)
    if not isinstance(metadata, Mapping):
        metadata = {}
    stats = metadata.get("completion_latency")
    if not isinstance(stats, Mapping):
        stats = metadata.get("ttft")
    if not isinstance(stats, Mapping):
        stats = {}
    return {
        "average": _number(stats.get("average")),
        "min": _number(stats.get("min")),
        "max": _number(stats.get("max")),
        "unit": stats.get("unit", "seconds"),
    }


def result_fields(result):
    """Retain task and token fields in their original insertion order."""
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
        "exposed_tools": result.get("exposed_tools", []),
        "golden_action": result.get("golden_action", []),
        "golden_fields": result.get("golden_fields", []),
        "context_tests": result.get("context_tests", []),
        "long_term_tests": result.get("long_term_tests", []),
        "minimum_steps": result.get("minimum_steps"),
        "data_flow": result.get("data_flow", []),
        "error_injection": result.get("error_injection"),
        "fallback_options": result.get("fallback_options", []),
        "resp_schema": result.get("resp_schema", {}),
        "arg_schema": result.get("arg_schema", {}),
        "repetitions": result.get("repetitions", 1),
        "repetition_results": result.get("repetition_results", []),
    }
    return simplified


def simplified_tool_calls(result):
    """Keep tool call fields and successful nonempty results."""
    tool_calls = []
    for invocation in result.get("tool_calls", []):
        tool_call = {
            "step": invocation.get("step"),
            "tool_name": invocation.get("tool_name"),
            "arguments": invocation.get("arguments"),
            "success": invocation.get("success"),
            "error": invocation.get("error")
        }

        # Include API result if available and successful
        if invocation.get("success") and invocation.get("result"):
            tool_call["result"] = invocation["result"]

        tool_calls.append(tool_call)

    return tool_calls


def format_message(msg):
    """Format a single message for logging."""
    role = msg.get("role", "unknown")
    content = msg.get("content", "")

    # For tool messages, include tool_call_id
    if role == "tool":
        tcid = msg.get("tool_call_id")
        # Try to parse and format tool result
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

    # For user/assistant messages, return as-is
    return {"role": role, "content": content}


def conversation_fields(result):
    """Format the conversation, retaining the nonfatal logging error field."""
    simplified = {}
    # Store complete conversation log for multi-turn scenarios
    try:
        conv = (result.get("result") or {}).get("conversation") or []
        total_msgs = len(conv)

        # Store complete conversation log
        simplified["conversation_log"] = {
            "total_messages": total_msgs,
            "messages": [format_message(m) for m in conv]
        }

    except Exception as e:
        # Non-fatal: skip conversation logging if structure unexpected
        simplified["conversation_log_error"] = str(e)

    return simplified


def final_response(result):
    """Extract the final response with the original truthiness rule."""
    # Extract final response
    if result.get("result") and result["result"].get("final_response"):
        return result["result"]["final_response"]
    else:
        return None


def result_statistics(simplified_results):
    """Calculate numeric metadata with the original rounding and key order."""
    # Calculate statistics
    total_tasks = len(simplified_results)
    successful_tasks = sum(1 for r in simplified_results if r.get('success', False))
    total_time = sum(r.get('execution_time', 0) for r in simplified_results)
    total_steps = sum(r.get('steps_taken', 0) for r in simplified_results)
    total_tool_calls = sum(len(r.get('tool_calls', [])) for r in simplified_results)

    # 토큰 통계 추가
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_tokens = 0

    for result in simplified_results:
        token_usage = result.get('token_usage', {})
        total_prompt_tokens += token_usage.get('prompt_tokens', 0)
        total_completion_tokens += token_usage.get('completion_tokens', 0)
        total_tokens += token_usage.get('total_tokens', 0)

    # TPS 계산
    average_tps = total_tokens / total_time if total_time > 0 else 0

    return {
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
    }


def tool_usage_statistics(simplified_results):
    """Count each tool usage and preserve first-seen tool order."""
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

    return tool_usage_stats


def assemble_log_data(metadata, statistics, observability, tool_usage, simplified_results):
    """Assemble ordered metadata, tool usage and task records."""
    return {
        "metadata": {**metadata, **statistics, **observability},
        "tool_usage_statistics": tool_usage,
        "results": simplified_results,
    }


def write_result_file(filepath, log_data):
    """Write UTF-8 JSON without a trailing LF to filepath."""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False)

    return str(filepath)


def token_usage_fields(result):
    """Retain supplied usage, including explicit None, or build zero defaults."""
    return {
        "token_usage": result.get("token_usage", {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }),
    }
