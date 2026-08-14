"""Deterministic metrics missing from the vendored registry."""

import json
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


def redundant_call_rate_det(ctx) -> float:
    """Close the no successful call -> 1.0 hole; 0.0, not None, keeps no-call tasks averaged."""
    successful_calls = sum(1 for a in ctx.action_trace if a.get("success"))
    if successful_calls == 0:
        return 0.0
    return load_metrics_module().METRICS["RedundantCallRate"].evaluate(ctx).score


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
