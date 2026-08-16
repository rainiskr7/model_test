"""Deterministic metrics missing from the vendored registry."""

import numbers
import re
from typing import Optional

try:
    from .context import load_metrics_module
except ImportError:  # direct file loading in tests
    from context import load_metrics_module


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


def redundant_call_rate_det(ctx) -> Optional[float]:
    """툴 호출이 없으면 '중복 호출률'은 정의되지 않는다 → None (0.0 아님)."""
    if not ctx.action_trace:
        return None
    return load_metrics_module().METRICS["RedundantCallRate"].evaluate(ctx).score


def _model_calls(ctx):
    action_trace = getattr(ctx, "action_trace", None)
    if action_trace:
        return action_trace
    logs = getattr(ctx, "logs", {}) or {}
    return logs.get("tool_calls", []) or []


def _call_tool(call):
    return call.get("tool") or call.get("tool_name")


def _call_args(call):
    return call.get("args") or call.get("arguments") or {}


def _argument_value_matches(actual, expected) -> bool:
    if isinstance(actual, str) and isinstance(expected, str):
        return actual.strip().casefold() == expected.strip().casefold()
    if (
        isinstance(actual, numbers.Number)
        and not isinstance(actual, bool)
        and isinstance(expected, numbers.Number)
        and not isinstance(expected, bool)
    ):
        return actual == expected
    return actual == expected


def context_retention_det(ctx) -> Optional[float]:
    context_tests = ctx.task_schema.get("context_tests", []) or []
    if not context_tests:
        return None

    calls = _model_calls(ctx)
    satisfied = 0
    for context_test in context_tests:
        expected_action = context_test.get("expected_action", {})
        expected_tool = expected_action.get("tool")
        expected_args = expected_action.get("args", {}) or {}

        # Turn alignment is deliberately not enforced yet because saved action traces
        # do not reliably retain dataset turn numbers; a matching call anywhere counts.
        matched = any(
            expected_tool is not None
            and _call_tool(call) == expected_tool
            and all(
                key in _call_args(call)
                and _argument_value_matches(_call_args(call)[key], value)
                for key, value in expected_args.items()
            )
            for call in calls
        )
        satisfied += int(matched)

    return satisfied / len(context_tests)


_MISSING = object()
_FIELD_PART = re.compile(r"^([^\[\]]+)((?:\[\d+\])*)$")


def _field_value(response, field_name):
    current = response
    for part in field_name.split("."):
        match = _FIELD_PART.fullmatch(part)
        if not match or not isinstance(current, dict) or match.group(1) not in current:
            return _MISSING
        current = current[match.group(1)]
        for index_text in re.findall(r"\[(\d+)\]", match.group(2)):
            index = int(index_text)
            if not isinstance(current, list) or index >= len(current):
                return _MISSING
            current = current[index]
    return current


def _tool_responses(ctx):
    logs = getattr(ctx, "logs", {}) or {}
    conversation = logs.get("conversation_log", {}) or {}
    messages = conversation.get("messages", []) or []

    tool_by_call_id = {}
    for message in messages:
        if message.get("role") != "assistant":
            continue
        for call in message.get("tool_calls", []) or []:
            call_id = call.get("id") or call.get("tool_call_id")
            function = call.get("function", {}) or {}
            tool_name = function.get("name") or _call_tool(call)
            if call_id and tool_name:
                tool_by_call_id[call_id] = tool_name

    calls = _model_calls(ctx)
    responses = []
    for message in messages:
        if message.get("role") != "tool" or not isinstance(message.get("content"), dict):
            continue
        content = message["content"]
        tool_name = (
            message.get("name")
            or message.get("tool_name")
            or tool_by_call_id.get(message.get("tool_call_id"))
        )
        if not tool_name:
            tool_name = next(
                (
                    _call_tool(call)
                    for call in calls
                    if _call_tool(call) and call.get("result") == content
                ),
                None,
            )
        responses.append((tool_name, content))
    return responses


def _value_appears(value, final_response) -> bool:
    response_text = str(final_response or "")
    if isinstance(value, numbers.Number) and not isinstance(value, bool):
        normalized_response = re.sub(
            r"(?<=\d)\.0(?!\d)", "", response_text.replace(",", "")
        )
        normalized_value = str(value).replace(",", "")
        if normalized_value.endswith(".0"):
            normalized_value = normalized_value[:-2]
        return bool(
            normalized_value
            and re.search(
                rf"(?<![\d.]){re.escape(normalized_value)}(?![\d.])",
                normalized_response,
            )
        )
    value_text = str(value).casefold()
    return bool(value_text and value_text in response_text.casefold())


def ref_recall_det(ctx) -> Optional[float]:
    golden_fields = ctx.task_schema.get("golden_fields", []) or []
    if not golden_fields:
        return None

    responses = _tool_responses(ctx)
    resolved = []
    for golden_entry in golden_fields:
        tool_name = golden_entry.get("tool")
        response = next(
            (content for tool, content in reversed(responses) if tool == tool_name),
            None,
        )
        if response is None:
            return None
        resolved.append((golden_entry, response))

    final_response = (getattr(ctx, "logs", {}) or {}).get("final_response", "")
    satisfied = 0
    for golden_entry, response in resolved:
        values = [_field_value(response, name) for name in golden_entry.get("fields", [])]
        if all(
            value is not _MISSING and _value_appears(value, final_response)
            for value in values
        ):
            satisfied += 1
    return satisfied / len(golden_fields)
