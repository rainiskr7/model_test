"""Deterministic metrics missing from the vendored registry."""

import json
from typing import Any, Optional

try:
    from .context import load_metrics_module
    from .l6_context import (
        l6_golden_field_diagnostics,
        normalize_field_value,
    )
except ImportError:  # direct file loading in tests
    from context import load_metrics_module
    from l6_context import (
        l6_golden_field_diagnostics,
        normalize_field_value,
    )


def l4_has_meaningful_result(result: Any) -> bool:
    if isinstance(result, list):
        return bool(result)
    if isinstance(result, dict):
        if not result:
            return False
        list_values = [value for value in result.values() if isinstance(value, list)]
        if list_values:
            return any(bool(value) for value in list_values)
        return True
    return result is not None and result != ""


def fsm_prefix(ctx) -> float:
    golden_action = ctx.task_schema.get("golden_action", [])
    if isinstance(golden_action, dict):
        golden_action = [golden_action]
    golden = [
        g["tool"]
        for g in golden_action
        if isinstance(g, dict) and g.get("tool")
    ]
    actual = [a.get("tool") for a in ctx.action_trace]
    return 1.0 if golden and actual[: len(golden)] == golden else 0.0


def arg_f1_det(ctx) -> Optional[float]:
    metrics = load_metrics_module()
    prf = metrics.ArgAccMetric._compute_prf(ctx)
    if not prf.get("ok"):
        return None
    return prf.get("f1")


def coverage_det(ctx) -> float:
    golden_action = ctx.task_schema.get("golden_action", [])
    required_tools = [action.get("tool") for action in golden_action if action.get("tool")]

    if not required_tools:
        return 1.0

    action_trace = ctx.action_trace
    successful_tools = set()

    for action in action_trace:
        tool_name = action.get("tool")
        success = action.get("success", False)

        if success and tool_name:
            result = action.get("result")
            if l4_has_meaningful_result(result):
                successful_tools.add(tool_name)

    covered_tools = [tool for tool in required_tools if tool in successful_tools]

    unique_required = list(set(required_tools))
    unique_covered = list(set(covered_tools))

    return len(unique_covered) / len(unique_required) if unique_required else 0.0


def source_epr_det(ctx) -> float:
    golden_action = ctx.task_schema.get("golden_action", [])
    required_tools = [action.get("tool") for action in golden_action if action.get("tool")]

    if not required_tools:
        return 1.0

    unique_tools = list(set(required_tools))
    action_trace = ctx.action_trace

    all_epr_values = []

    for tool_name in unique_tools:
        tool_calls = [
            action for action in action_trace
            if action.get("tool") == tool_name
        ]

        if not tool_calls:
            all_epr_values.append(0.0)
            continue

        valid_calls = 0
        for call in tool_calls:
            success = call.get("success", False)
            error = call.get("error")

            if success and not error and l4_has_meaningful_result(call.get("result")):
                valid_calls += 1

        epr = valid_calls / len(tool_calls)
        all_epr_values.append(epr)

    return sum(all_epr_values) / len(all_epr_values) if all_epr_values else 0.0


def golden_field_recall_det(ctx) -> Optional[float]:
    """At L6, zero new tool calls are correct under seed_replay; this measures whether seeded facts survived into the answer."""
    diagnostics = l6_golden_field_diagnostics(ctx)
    if diagnostics["seeded_echo"]:
        return 0.0

    scorable_values = diagnostics["scorable_values"]
    if not scorable_values:
        return None

    response = ctx.logs.get("final_response")
    if response is None:
        response = ""
    normalized_response = normalize_field_value(response)
    hits = sum(
        1
        for value in scorable_values
        if normalize_field_value(value) and normalize_field_value(value) in normalized_response
    )
    return hits / len(scorable_values)


def no_refetch_det(ctx) -> float:
    """At L6, zero new tool calls is correct because seed_replay already seeds prior tool results; this axis is deliberately separate from answer correctness."""
    return 1.0 if len(ctx.action_trace) == 0 else 0.0


def call_eff_det(ctx) -> Optional[float]:
    actual_calls = len(ctx.action_trace)
    minimum_calls = ctx.task_schema.get("minimum_calls")

    if minimum_calls is None:
        golden_action = ctx.task_schema.get("golden_action", [])
        if isinstance(golden_action, dict):
            golden_action = [golden_action]
        unique_tools = set()
        for action in golden_action:
            if isinstance(action, dict):
                tool = action.get("tool")
                if tool:
                    args_str = json.dumps(action.get("args", {}), sort_keys=True)
                    unique_tools.add((tool, args_str))
        minimum_calls = len(unique_tools) if unique_tools else 1

    if actual_calls <= 0:
        return 0.0
    return min(1.0, minimum_calls / actual_calls)
