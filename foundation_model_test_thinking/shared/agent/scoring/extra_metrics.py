"""Deterministic metrics missing from the vendored registry."""

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
