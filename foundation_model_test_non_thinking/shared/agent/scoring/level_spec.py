"""Metric lists and aggregation rules for deterministic agent scoring."""

from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional, Sequence

try:
    from .extra_metrics import (
        arg_f1_det,
        context_retention_det,
        fsm_prefix,
        redundant_call_rate_det,
        refetch_avoidance_det,
        result_field_coverage_det,
        result_field_coverage_diagnostics,
        seeded_field_recall_det,
        seeded_field_recall_diagnostics,
    )
except ImportError:  # direct file loading in tests
    from extra_metrics import (
        arg_f1_det,
        context_retention_det,
        fsm_prefix,
        redundant_call_rate_det,
        refetch_avoidance_det,
        result_field_coverage_det,
        result_field_coverage_diagnostics,
        seeded_field_recall_det,
        seeded_field_recall_diagnostics,
    )


JUDGE_METRICS = ("SR", "ArgAcc", "EffScore", "ContextRetention", "RefRecall")
COMMON_RECORD_ONLY = ("pass@k", "RespOK")


@dataclass(frozen=True)
class MetricSpec:
    name: str
    producer: Callable
    in_score: bool
    diagnostic_producer: Optional[Callable] = None


def vendored_metric(metric_name: str):
    def _evaluate(ctx):
        try:
            from .context import load_metrics_module
        except ImportError:
            from context import load_metrics_module

        metric = load_metrics_module().METRICS[metric_name]
        return metric.evaluate(ctx).score

    return _evaluate


LEVEL_SPECS = {
    "L1": (
        MetricSpec("ToolAcc", vendored_metric("ToolAcc"), True),
        MetricSpec("CallEM", vendored_metric("CallEM"), True),
        MetricSpec("ArgF1_det", arg_f1_det, True),
    ),
    "L2": (MetricSpec("SelectAcc", vendored_metric("SelectAcc"), True),),
    "L3": (
        MetricSpec("FSM_strict", vendored_metric("FSM"), True),
        MetricSpec("PSM", vendored_metric("PSM"), True),
        MetricSpec("ΔSteps_norm", vendored_metric("ΔSteps_norm"), True),
        MetricSpec("FSM_prefix", fsm_prefix, False),
    ),
    "L4": (
        MetricSpec("Coverage", vendored_metric("Coverage"), True),
        MetricSpec("SourceEPR", vendored_metric("SourceEPR"), True),
    ),
    "L5": (
        MetricSpec("FallbackSR", vendored_metric("FallbackSR"), True),
        MetricSpec("AdaptiveRoutingScore", vendored_metric("AdaptiveRoutingScore"), True),
        MetricSpec("EPR_CVR", vendored_metric("EPR_CVR"), True),
    ),
    "L6": (
        MetricSpec("ToolAcc", vendored_metric("ToolAcc"), True),
        MetricSpec("RedundantCallRate", redundant_call_rate_det, True),
    ),
    # Record-only in agent_det_v2: L7 does not contribute to agent_score until both
    # metrics apply to most tasks across models and tool-call rate is high enough that
    # coverage is not success-conditioned; promotion also bumps the scoring version.
    # Upstream RefRecall is
    # judge-only conversational fact recall from the transcript; result-field coverage
    # is a different construct, so do not conflate them or rename it back.
    "L7": (
        MetricSpec("ContextRetention_det", context_retention_det, False),
        MetricSpec(
            "ResultFieldCoverage_det",
            result_field_coverage_det,
            False,
            result_field_coverage_diagnostics,
        ),
    ),
}


# Frozen published v2 remains ``LEVEL_SPECS``. V3 is a separate contract: all
# levels are identical except L6, whose golden action is context reuse rather
# than another tool invocation.
LEVEL_SPECS_V3 = dict(LEVEL_SPECS)
LEVEL_SPECS_V3["L6"] = (
    MetricSpec("RefetchAvoidance_det", refetch_avoidance_det, True),
    MetricSpec(
        "SeededFieldRecall_det",
        seeded_field_recall_det,
        True,
        seeded_field_recall_diagnostics,
    ),
)


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
