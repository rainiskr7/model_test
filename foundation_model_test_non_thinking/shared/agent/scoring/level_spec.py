"""Metric lists and aggregation rules for deterministic agent scoring."""

from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional, Sequence

try:
    from .context import load_vendored_metric
    from .extra_metrics import (
        arg_f1_det,
        call_eff_det,
        coverage_det,
        fsm_prefix,
        golden_field_recall_det,
        no_refetch_det,
        source_epr_det,
    )
except ImportError:  # direct file loading in tests
    from context import load_vendored_metric
    from extra_metrics import (
        arg_f1_det,
        call_eff_det,
        coverage_det,
        fsm_prefix,
        golden_field_recall_det,
        no_refetch_det,
        source_epr_det,
    )


JUDGE_METRICS = ("SR", "ArgAcc", "EffScore", "ContextRetention", "RefRecall")
COMMON_RECORD_ONLY = ("pass@k", "RespOK")
PASSK_PRIMARY_METRICS = {
    "L1": "CallEM",
    "L2": "SelectAcc",
    # FSM_strict is count-based and near-duplicate of ΔSteps_norm; FSM_prefix is the sequence primary.
    "L3": "FSM_prefix",
    # Vendored Coverage only recognizes search-shaped responses, so L4 pass@k uses the deterministic predicate.
    "L4": "Coverage_det",
    "L5": "FallbackSR",
    # In L6 seed_replay, the correct behavior is zero new tool calls; call-based
    # metrics cannot be the pass@k primary.
    "L6": "GoldenFieldRecall_det",
    "L7": "ToolAcc",
}


@dataclass(frozen=True)
class MetricSpec:
    name: str
    producer: Callable
    in_score: bool


def vendored_metric(metric_name: str):
    def _evaluate(ctx):
        return load_vendored_metric(metric_name).evaluate(ctx).score

    return _evaluate


LEVEL_SPECS = {
    "L1": (
        MetricSpec("ToolAcc", vendored_metric("ToolAcc"), True),
        MetricSpec("CallEM", vendored_metric("CallEM"), True),
        MetricSpec("ArgF1_det", arg_f1_det, True),
    ),
    "L2": (
        MetricSpec("SelectAcc", vendored_metric("SelectAcc"), True),
        MetricSpec("CallEM", vendored_metric("CallEM"), True),
        MetricSpec("ArgF1_det", arg_f1_det, True),
    ),
    "L3": (
        MetricSpec("FSM_prefix", fsm_prefix, True),
        MetricSpec("FSM_strict", vendored_metric("FSM"), False),
        MetricSpec("PSM", vendored_metric("PSM"), True),
        MetricSpec("ΔSteps_norm", vendored_metric("ΔSteps_norm"), True),
        MetricSpec("ArgF1_det", arg_f1_det, True),
    ),
    "L4": (
        MetricSpec("Coverage_det", coverage_det, True),
        MetricSpec("SourceEPR_det", source_epr_det, True),
        MetricSpec("Coverage", vendored_metric("Coverage"), False),
        MetricSpec("SourceEPR", vendored_metric("SourceEPR"), False),
    ),
    "L5": (
        MetricSpec("FallbackSR", vendored_metric("FallbackSR"), True),
        MetricSpec("AdaptiveRoutingScore", vendored_metric("AdaptiveRoutingScore"), True),
        MetricSpec("EPR_CVR", vendored_metric("EPR_CVR"), True),
    ),
    "L6": (
        MetricSpec("GoldenFieldRecall_det", golden_field_recall_det, True),
        MetricSpec("NoRefetch_det", no_refetch_det, True),
        MetricSpec("RedundantCallRate", vendored_metric("RedundantCallRate"), False),
        MetricSpec("ToolAcc", vendored_metric("ToolAcc"), False),
        MetricSpec("Coverage", vendored_metric("Coverage"), False),
        MetricSpec("CallEff_det", call_eff_det, False),
    ),
    "L7": (
        MetricSpec("ToolAcc", vendored_metric("ToolAcc"), True),
        MetricSpec("CallEM", vendored_metric("CallEM"), True),
        MetricSpec("ArgF1_det", arg_f1_det, True),
    ),
}


def mean_or_none(values: Iterable[Optional[float]]) -> Optional[float]:
    present = [v for v in values if v is not None]
    if not present:
        return None
    return sum(present) / len(present)


def representative_score(entries: Sequence[dict]) -> Optional[float]:
    return mean_or_none(
        entry.get("score")
        for entry in entries
        if entry.get("in_score") and entry.get("score") is not None
    )


def level_score(metrics: dict) -> Optional[float]:
    return representative_score(list(metrics.values()))
