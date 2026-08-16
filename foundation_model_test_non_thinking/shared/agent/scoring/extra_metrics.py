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


_NUMBER_LITERAL = re.compile(
    r"(?<![\d.,])[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?![\d.,])"
)
_HTML_TAG = re.compile(r"<[^>]*>")


def _normalized_text(value) -> str:
    without_tags = _HTML_TAG.sub(" ", str(value))
    return " ".join(without_tags.split()).casefold()


def _value_appears(value, final_response) -> bool:
    response_text = str(final_response or "")
    if isinstance(value, numbers.Number) and not isinstance(value, bool):
        for match in _NUMBER_LITERAL.finditer(response_text):
            literal = match.group(0)
            decimals = min(len(literal.rsplit(".", 1)[1]), 6) if "." in literal else 0
            candidate = float(literal.replace(",", ""))
            if round(float(value), decimals) == round(candidate, decimals):
                return True
        return False
    value_text = _normalized_text(value)
    return bool(value_text and value_text in _normalized_text(response_text))


def _result_field_coverage(ctx):
    golden_fields = ctx.task_schema.get("golden_fields", []) or []
    diagnostics = {
        "fields_required": sum(
            len(entry.get("fields", [])) for entry in golden_fields
        ),
        "fields_checked": 0,
        "fields_excluded_long_text": 0,
        "fields_unresolved": 0,
    }
    if not golden_fields:
        return None, diagnostics

    responses = _tool_responses(ctx)
    resolved = []
    for golden_entry in golden_fields:
        response = next(
            (
                content
                for tool, content in reversed(responses)
                if tool == golden_entry.get("tool")
            ),
            None,
        )
        if response is None:
            return None, diagnostics
        resolved.append((golden_entry, response))

    final_response = (getattr(ctx, "logs", {}) or {}).get("final_response", "")
    satisfied = 0
    judged = 0
    for golden_entry, response in resolved:
        entry_judged = False
        entry_satisfied = True
        for field_name in golden_entry.get("fields", []):
            value = _field_value(response, field_name)
            if value is _MISSING:
                diagnostics["fields_unresolved"] += 1
                entry_judged = True
                entry_satisfied = False
                continue
            if not isinstance(value, numbers.Number) or isinstance(value, bool):
                if len(_normalized_text(value)) > 80:
                    diagnostics["fields_excluded_long_text"] += 1
                    continue
            diagnostics["fields_checked"] += 1
            entry_judged = True
            if not _value_appears(value, final_response):
                entry_satisfied = False

        if not entry_judged:
            continue
        judged += 1
        if entry_satisfied:
            satisfied += 1
    return (satisfied / judged if judged else None), diagnostics


def result_field_coverage_det(ctx) -> Optional[float]:
    # Upstream RefRecall is judge-only and measures conversational fact recall from
    # the message transcript. This checks golden-field values in the final answer,
    # which is a different construct; do not conflate them or rename this back.
    return _result_field_coverage(ctx)[0]


def result_field_coverage_diagnostics(ctx):
    return _result_field_coverage(ctx)[1]
