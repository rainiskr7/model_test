"""Dependency-free builders for agent result observability metadata."""

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
