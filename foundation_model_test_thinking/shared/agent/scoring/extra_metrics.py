"""Deterministic metrics missing from the vendored registry."""

import json
import re
from typing import Any, Dict, List, Optional, Tuple

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


def _int_or_none(value) -> Optional[int]:
    try:
        return int(value)
    except Exception:
        return None


def l6_evaluation_turn(task_schema: Dict[str, Any]) -> int:
    tracking = task_schema.get("conversation_tracking") or {}
    eval_ctx = tracking.get("evaluation_context") or {}
    context_tests = eval_ctx.get("context_tests") or []
    turns = tracking.get("turns") or []

    test_turns = []
    if isinstance(context_tests, list):
        for test in context_tests:
            if isinstance(test, dict) and test.get("turn") is not None:
                turn = _int_or_none(test.get("turn"))
                if turn is not None:
                    test_turns.append(turn)
    if test_turns:
        return max(test_turns)

    user_turns = []
    if isinstance(turns, list):
        for turn in turns:
            if not isinstance(turn, dict) or turn.get("role") != "user":
                continue
            turn_number = _int_or_none(turn.get("turn_number"))
            if turn_number is not None:
                user_turns.append(turn_number)
    return max(user_turns) if user_turns else 1


def l6_seeded_context(task_schema: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any]]:
    evaluation_turn = l6_evaluation_turn(task_schema)
    tracking = task_schema.get("conversation_tracking") or {}
    turns = tracking.get("turns") or []
    seeded_texts: List[str] = []
    seeded_results: Dict[str, Any] = {}
    if not isinstance(turns, list):
        return seeded_texts, seeded_results

    for turn in turns:
        if not isinstance(turn, dict):
            continue
        turn_number = _int_or_none(turn.get("turn_number"))
        if turn_number is None or turn_number > evaluation_turn:
            continue
        if turn.get("role") != "assistant":
            continue

        content = turn.get("content")
        if isinstance(content, str) and content.strip():
            seeded_texts.append(content.strip())

        actions = []
        if isinstance(turn.get("action"), dict):
            actions = [turn.get("action")]
        elif isinstance(turn.get("actions"), list):
            actions = turn.get("actions")

        for action in actions:
            if not isinstance(action, dict):
                continue
            tool = action.get("tool")
            if tool and action.get("result") is not None and tool not in seeded_results:
                seeded_results[tool] = action.get("result")

    return seeded_texts, seeded_results


_PATH_SEGMENT_RE = re.compile(r"^([^\[\]]+)(?:\[(\d+)\])?$")


def l6_resolve_field(result: Any, path: str) -> Tuple[bool, Any]:
    current = result
    for segment in str(path).split("."):
        match = _PATH_SEGMENT_RE.match(segment)
        if not match or not isinstance(current, dict):
            return False, None
        key, index = match.groups()
        if key not in current:
            return False, None
        current = current[key]
        if index is not None:
            if not isinstance(current, list):
                return False, None
            idx = int(index)
            if idx >= len(current):
                return False, None
            current = current[idx]
    if current is None:
        return False, None
    return True, current


def l6_resolve_field_with_fallback(result: Any, path: str) -> Tuple[bool, Any, bool]:
    resolved, value = l6_resolve_field(result, path)
    if resolved:
        return True, value, False
    if not isinstance(result, dict):
        return False, None, False

    segments = str(path).split(".")
    last_match = _PATH_SEGMENT_RE.match(segments[-1]) if segments else None
    if not last_match:
        return False, None, False
    leaf, leaf_index = last_match.groups()

    parent_index = None
    if len(segments) >= 2:
        parent_match = _PATH_SEGMENT_RE.match(segments[-2])
        if parent_match and parent_match.group(2) is not None:
            parent_index = int(parent_match.group(2))

    idx = parent_index
    if idx is None:
        idx = int(leaf_index) if leaf_index is not None else 0

    candidates = []
    for key, candidate in result.items():
        if (
            isinstance(candidate, list)
            and candidate
            and isinstance(candidate[0], dict)
            and leaf in candidate[0]
        ):
            if idx < len(candidate) and isinstance(candidate[idx], dict):
                candidates.append(candidate[idx].get(leaf))
        elif isinstance(candidate, dict) and leaf in candidate:
            candidates.append(candidate[leaf])
        elif not isinstance(candidate, (list, dict)) and key.endswith(leaf) and key != leaf:
            candidates.append(candidate)

    if len(candidates) == 1 and candidates[0] is not None:
        return True, candidates[0], True
    return False, None, False


def l6_is_filtered_field(path: str) -> bool:
    last_segment = str(path).split(".")[-1]
    field_name = re.sub(r"\[\d+\]$", "", last_segment)
    return field_name in {"description", "contents"}


def _normalize_field_value(value: Any) -> str:
    text = re.sub(r"<[^>]{1,10}>", "", str(value))
    text = re.sub(r"[\s,]+", "", text)
    return text.lower()


def l6_golden_field_diagnostics(ctx) -> Dict[str, Any]:
    task_schema = ctx.task_schema
    seeded_texts, seeded_results = l6_seeded_context(task_schema)
    response = ctx.logs.get("final_response")
    if response is None:
        response = ""
    response_text = str(response).strip()

    scorable_values = []
    unresolved_fields = 0
    fallback_fields = 0
    golden_fields = task_schema.get("golden_fields") or []
    if isinstance(golden_fields, list):
        for entry in golden_fields:
            if not isinstance(entry, dict):
                continue
            tool = entry.get("tool")
            fields = entry.get("fields") or []
            if not isinstance(fields, list):
                continue
            result = seeded_results.get(tool)
            if result is None:
                unresolved_fields += len(fields)
                continue
            for field in fields:
                resolved, value, used_fallback = l6_resolve_field_with_fallback(result, field)
                if not resolved:
                    unresolved_fields += 1
                    continue
                if used_fallback:
                    fallback_fields += 1
                if not l6_is_filtered_field(field):
                    scorable_values.append(value)

    return {
        "seeded_echo": bool(response_text) and response_text in seeded_texts,
        "unresolved_fields": unresolved_fields,
        "fallback_fields": fallback_fields,
        "scorable_values": scorable_values,
    }


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
    normalized_response = _normalize_field_value(response)
    hits = sum(
        1
        for value in scorable_values
        if _normalize_field_value(value) and _normalize_field_value(value) in normalized_response
    )
    return hits / len(scorable_values)


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
