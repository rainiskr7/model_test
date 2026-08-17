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
    """툴 호출이 없으면 '중복 호출률'은 정의되지 않는다 → None (0.0 아님).

    Vendored RedundantCallRate is ``1 - redundant_calls / reuse_opportunities``.
    Its redundant-call numerator is unbounded while the pinned golden actions
    provide only one or two ``context_used`` reuse opportunities, so the
    formula can legitimately produce a negative contract-violating value.
    """
    if not ctx.action_trace:
        return None
    return load_metrics_module().METRICS["RedundantCallRate"].evaluate(ctx).score


def refetch_avoidance_det(ctx) -> Optional[float]:
    """Reward the reference L6 behavior: answer without a new evaluation-turn call.

    ``freshness_threshold`` is intentionally ignored. The fixture timestamp is
    2025-09-27 while the evaluated runs are from 2026-08-16, so a literal 24-hour
    comparison would declare every seeded result stale despite the golden
    ``context_used`` action. It would also make a saved trace change score as time
    passes. ``minimum_calls`` describes the already-seeded conversation, not the
    single evaluation turn, and is ignored for the same reference-behavior reason.
    """
    logs = getattr(ctx, "logs", {}) or {}
    if logs.get("_new_call_trace_present") is False:
        return None

    trace = getattr(ctx, "action_trace", None)
    if trace is None:
        if "tool_calls" not in logs:
            return None
        trace = logs.get("tool_calls")
    if not isinstance(trace, list):
        return None
    return 1.0 if not trace else 0.0


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


def _seeded_tool_responses(ctx):
    """Return only payloads attached to ``seed_call_*`` ids.

    Model-generated re-fetches can appear later in the same conversation. They
    must never replace the seeded payload used by L6 recall scoring.
    """
    logs = getattr(ctx, "logs", {}) or {}
    conversation = logs.get("conversation_log", {}) or {}
    messages = conversation.get("messages", []) or []

    tool_by_call_id = {}
    for message in messages:
        if message.get("role") != "assistant":
            continue
        for call in message.get("tool_calls", []) or []:
            call_id = call.get("id") or call.get("tool_call_id")
            if not isinstance(call_id, str) or not call_id.startswith("seed_call_"):
                continue
            function = call.get("function", {}) or {}
            tool_name = function.get("name") or _call_tool(call)
            if tool_name:
                tool_by_call_id[call_id] = tool_name

    responses = []
    for message in messages:
        call_id = message.get("tool_call_id")
        if (
            message.get("role") != "tool"
            or not isinstance(call_id, str)
            or not call_id.startswith("seed_call_")
            or not isinstance(message.get("content"), dict)
        ):
            continue
        responses.append(
            (
                message.get("name")
                or message.get("tool_name")
                or tool_by_call_id.get(call_id),
                message["content"],
                call_id,
            )
        )
    return responses


def _resolve_seeded_golden_fields(ctx, golden_fields):
    """Resolve declarations only against persisted ``seed_call_*`` payloads.

    Saved artifacts can omit the seeded assistant ``tool_calls`` that carried the
    tool name. L7 therefore maps an unnamed seed only when its encoded turn is
    identified by context-test metadata; payload shape alone is not enough because
    several unrelated calls can return the same schema. L6's single-seed fixture
    remains unambiguous without turn metadata.
    """
    seeded = _seeded_tool_responses(ctx)
    if not seeded:
        return None

    resolved = []
    for golden_entry in golden_fields:
        context_tests = ctx.task_schema.get("context_tests", []) or []
        long_term_tests = ctx.task_schema.get("long_term_tests", []) or []
        tool_name = golden_entry.get("tool")
        target_turns = set()
        if len(golden_fields) == 1 and (context_tests or long_term_tests):
            final_test_turn = max(
                (test.get("turn") for test in context_tests if test.get("turn") is not None),
                default=None,
            )
            target_turns = {
                test.get("turn")
                for test in context_tests
                if test.get("turn") == final_test_turn
                and (test.get("expected_action") or {}).get("tool") == tool_name
            }
            if not target_turns:
                target_turns = {
                    int(test["plant_turn"]) + 1
                    for test in long_term_tests
                    if test.get("test_turn") == final_test_turn
                    and test.get("plant_turn") is not None
                }
        if target_turns:
            candidates = [
                content
                for tool, content, call_id in seeded
                if tool in {None, tool_name}
                and any(call_id.startswith(f"seed_call_{turn}_") for turn in target_turns)
            ]
        elif not context_tests and not long_term_tests:
            candidates = [
                content
                for tool, content, _call_id in seeded
                if tool == tool_name
            ]
            if not candidates and len(golden_fields) == 1 and len(seeded) == 1:
                candidates = [seeded[0][1]]
        else:
            candidates = []
        if not candidates:
            return None
        resolved.append((golden_entry, candidates[-1]))
    return resolved


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

    resolved = _resolve_seeded_golden_fields(ctx, golden_fields)
    if resolved is None:
        return None, diagnostics

    final_response = (getattr(ctx, "logs", {}) or {}).get("final_response", "")
    satisfied = 0
    judged = 0
    for golden_entry, response in resolved:
        entry_judged = False
        entry_satisfied = True
        entry_unresolved = False
        for field_name in golden_entry.get("fields", []):
            value = _field_value(response, field_name)
            if value is _MISSING:
                diagnostics["fields_unresolved"] += 1
                entry_unresolved = True
                continue
            if not isinstance(value, numbers.Number) or isinstance(value, bool):
                if len(_normalized_text(value)) > 80:
                    diagnostics["fields_excluded_long_text"] += 1
                    continue
            diagnostics["fields_checked"] += 1
            entry_judged = True
            if not _value_appears(value, final_response):
                entry_satisfied = False

        # An absent fixture value is unmeasurable benchmark data, not a model
        # miss. Exclude the whole declaration rather than turning it into zero.
        if entry_unresolved or not entry_judged:
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


def _seeded_field_recall(ctx):
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

    resolved_entries = _resolve_seeded_golden_fields(ctx, golden_fields)
    if resolved_entries is None:
        return None, diagnostics

    final_response = (getattr(ctx, "logs", {}) or {}).get("final_response", "")
    satisfied = 0
    judged = 0
    for golden_entry, response in resolved_entries:
        values = []
        entry_unresolved = False
        for field_name in golden_entry.get("fields", []):
            value = _field_value(response, field_name)
            if value is _MISSING:
                diagnostics["fields_unresolved"] += 1
                entry_unresolved = True
                continue
            if not isinstance(value, numbers.Number) or isinstance(value, bool):
                if len(_normalized_text(value)) > 80:
                    diagnostics["fields_excluded_long_text"] += 1
                    continue
            values.append(value)

        # A malformed declaration is benchmark data, not a model miss. Exclude
        # the whole golden-field entry rather than mixing its resolvable subset
        # into the model's score.
        if entry_unresolved:
            continue
        diagnostics["fields_checked"] += len(values)
        judged += len(values)
        satisfied += sum(_value_appears(value, final_response) for value in values)

    return (satisfied / judged if judged else None), diagnostics


def seeded_field_recall_det(ctx) -> Optional[float]:
    return _seeded_field_recall(ctx)[0]


def seeded_field_recall_diagnostics(ctx):
    return _seeded_field_recall(ctx)[1]
