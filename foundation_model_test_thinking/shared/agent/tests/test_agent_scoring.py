"""agent scoring 단독 실행 테스트.

패키지 import 없이 파일 경로에서 직접 로드한다.
"""

import contextlib
import importlib.util
import io
import os
import sys
from pathlib import Path


SCORING_DIR = Path(__file__).resolve().parents[1] / "scoring"


def _load_module(name):
    path = SCORING_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"{name}_under_test", path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SCORING_DIR))
    try:
        spec.loader.exec_module(module)
    finally:
        try:
            sys.path.remove(str(SCORING_DIR))
        except ValueError:
            pass
    return module


extra_metrics = _load_module("extra_metrics")
level_spec = _load_module("level_spec")
aggregate = _load_module("aggregate")
score_run = _load_module("score_run")
scoring_context = _load_module("context")


class DummyContext:
    def __init__(self, golden_action=None, action_trace=None, task_schema=None, logs=None):
        self.task_schema = {"golden_action": golden_action or []}
        self.task_schema.update(task_schema or {})
        self.action_trace = action_trace or []
        self.logs = logs or {}


def _assert(condition, message):
    if not condition:
        raise AssertionError(message)


def _assert_close(actual, expected, message):
    if actual is None or abs(actual - expected) > 1e-9:
        raise AssertionError(f"{message}: expected {expected}, got {actual}")


def test_fsm_prefix_exact_match():
    ctx = DummyContext([{"tool": "A"}, {"tool": "B"}], [{"tool": "A"}, {"tool": "B"}])
    _assert_close(extra_metrics.fsm_prefix(ctx), 1.0, "exact match")


def test_fsm_prefix_with_extra_calls():
    ctx = DummyContext(
        [{"tool": "A"}, {"tool": "B"}],
        [{"tool": "A"}, {"tool": "B"}, {"tool": "C"}],
    )
    _assert_close(extra_metrics.fsm_prefix(ctx), 1.0, "prefix with extra calls")


def test_fsm_prefix_wrong_order():
    ctx = DummyContext([{"tool": "A"}, {"tool": "B"}], [{"tool": "B"}, {"tool": "A"}])
    _assert_close(extra_metrics.fsm_prefix(ctx), 0.0, "wrong order")


def test_fsm_prefix_empty_golden():
    ctx = DummyContext([], [{"tool": "A"}])
    _assert_close(extra_metrics.fsm_prefix(ctx), 0.0, "empty golden")


def test_fsm_prefix_empty_actual():
    ctx = DummyContext([{"tool": "A"}], [])
    _assert_close(extra_metrics.fsm_prefix(ctx), 0.0, "empty actual")


def test_mean_excludes_none():
    _assert_close(level_spec.mean_or_none([1.0, None, 0.0]), 0.5, "None excluded")


def test_mean_all_none():
    _assert(level_spec.mean_or_none([None, None]) is None, "all None should be None")


def test_in_score_false_excluded():
    entries = [
        {"score": 1.0, "in_score": True},
        {"score": 0.0, "in_score": False},
    ]
    _assert_close(level_spec.representative_score(entries), 1.0, "in_score false excluded")


def test_context_exposes_l7_ground_truth_with_empty_defaults():
    expected = {
        "golden_fields": [{"tool": "Lookup", "fields": ["value"]}],
        "context_tests": [{"expected_action": {"tool": "Lookup", "args": {}}}],
        "long_term_tests": [{"plant_turn": 1, "test_turn": 5}],
    }
    task_schema, _logs = scoring_context.task_to_schema_and_logs(expected)
    for key, value in expected.items():
        _assert(task_schema[key] == value, f"{key} was not exposed to scoring")

    empty_schema, _logs = scoring_context.task_to_schema_and_logs({})
    for key in expected:
        _assert(empty_schema[key] == [], f"{key} default must be []")


def test_redundant_call_rate_empty_without_bench():
    original = extra_metrics.load_metrics_module

    def fail_if_called():
        raise AssertionError("vendored metrics must not be loaded")

    extra_metrics.load_metrics_module = fail_if_called
    try:
        ctx = DummyContext([], [])
        _assert(
            extra_metrics.redundant_call_rate_det(ctx) is None,
            "empty action trace should be not applicable",
        )
    finally:
        extra_metrics.load_metrics_module = original


def test_redundant_call_rate_nonempty_loads_bench():
    original = extra_metrics.load_metrics_module
    sentinel = RuntimeError("sentinel vendored load")

    def raise_sentinel():
        raise sentinel

    extra_metrics.load_metrics_module = raise_sentinel
    try:
        ctx = DummyContext([], [{"tool": "A"}])
        try:
            extra_metrics.redundant_call_rate_det(ctx)
        except RuntimeError as exc:
            _assert(exc is sentinel, "redundant call rate raised a different exception")
        else:
            raise AssertionError("non-empty action trace must load vendored metrics")
    finally:
        extra_metrics.load_metrics_module = original


def test_context_retention_det_all_with_normalization_and_extra_args():
    context_tests = [
        {
            "expected_action": {
                "tool": "Lookup",
                "args": {"query": " BTC ", "limit": 500},
            }
        },
        {"expected_action": {"tool": "Weather", "args": {"city": "SEOUL"}}},
    ]
    ctx = DummyContext(
        action_trace=[
            {
                "tool": "Lookup",
                "args": {"query": "btc", "limit": 500.0, "extra": True},
            },
            {"tool": "Weather", "args": {"city": "seoul"}},
        ],
        task_schema={"context_tests": context_tests},
    )
    _assert_close(
        extra_metrics.context_retention_det(ctx),
        1.0,
        "all context actions with normalized values and extra args",
    )

    fallback = DummyContext(
        task_schema={"context_tests": [context_tests[0]]},
        logs={
            "tool_calls": [
                {
                    "tool_name": "Lookup",
                    "arguments": {"query": "btc", "limit": 500.0, "extra": True},
                }
            ]
        },
    )
    _assert_close(
        extra_metrics.context_retention_det(fallback),
        1.0,
        "raw tool call fallback",
    )


def test_context_retention_det_partial_and_wrong_value():
    context_tests = [
        {"expected_action": {"tool": "Lookup", "args": {"symbol": "BTC"}}},
        {"expected_action": {"tool": "Lookup", "args": {"symbol": "ETH"}}},
    ]
    ctx = DummyContext(
        action_trace=[{"tool": "Lookup", "args": {"symbol": "BTC"}}],
        task_schema={"context_tests": context_tests},
    )
    _assert_close(
        extra_metrics.context_retention_det(ctx), 0.5, "half context actions matched"
    )

    wrong_value = DummyContext(
        action_trace=[{"tool": "Lookup", "args": {"symbol": "SOL"}}],
        task_schema={"context_tests": [context_tests[0]]},
    )
    _assert_close(
        extra_metrics.context_retention_det(wrong_value),
        0.0,
        "wrong argument value must not match",
    )


def test_context_retention_det_none_matched_and_no_data():
    ctx = DummyContext(
        action_trace=[{"tool": "Other", "args": {"symbol": "BTC"}}],
        task_schema={
            "context_tests": [
                {"expected_action": {"tool": "Lookup", "args": {"symbol": "BTC"}}}
            ]
        },
    )
    _assert_close(extra_metrics.context_retention_det(ctx), 0.0, "no actions matched")
    _assert(
        extra_metrics.context_retention_det(DummyContext()) is None,
        "no context tests must be not applicable",
    )


def _ref_recall_context(final_response, golden_fields=None, include_second=True):
    first_result = {
        "price": 1234.0,
        "item": [{"title": "Alpha Book"}],
    }
    second_result = {"author": "Beta Writer"}
    messages = [
        {"role": "tool", "tool_call_id": "call_1", "content": first_result},
    ]
    action_trace = [
        {"tool": "Catalog", "args": {}, "result": first_result},
    ]
    if include_second:
        messages.append(
            {"role": "tool", "tool_call_id": "call_2", "content": second_result}
        )
        action_trace.append({"tool": "Author", "args": {}, "result": second_result})
    return DummyContext(
        action_trace=action_trace,
        task_schema={
            "golden_fields": golden_fields
            if golden_fields is not None
            else [
                {"tool": "Catalog", "fields": ["price", "item[0].title"]},
                {"tool": "Author", "fields": ["author"]},
            ]
        },
        logs={
            "conversation_log": {"messages": messages},
            "final_response": final_response,
        },
    )


def test_ref_recall_det_all_and_partial():
    all_present = _ref_recall_context(
        "The price is 1,234 and the title is ALPHA BOOK by beta writer."
    )
    _assert_close(extra_metrics.ref_recall_det(all_present), 1.0, "all references recalled")

    one_missing = _ref_recall_context("The price is 1234.0; title: alpha book.")
    _assert_close(extra_metrics.ref_recall_det(one_missing), 0.5, "one reference missing")


def test_ref_recall_det_no_data_and_missing_tool_response():
    no_data = _ref_recall_context("anything", golden_fields=[])
    _assert(
        extra_metrics.ref_recall_det(no_data) is None,
        "no golden fields must be not applicable",
    )

    missing_response = _ref_recall_context("beta writer", include_second=False)
    _assert(
        extra_metrics.ref_recall_det(missing_response) is None,
        "missing required tool response must be not applicable",
    )


def test_l6_spec_wires_redundant_call_rate():
    specs = level_spec.LEVEL_SPECS["L6"]
    _assert(len(specs) == 2, "L6 must have exactly two metric specs")
    _assert(
        {spec.name for spec in specs} == {"ToolAcc", "RedundantCallRate"},
        "L6 metric names mismatch",
    )
    _assert(all(spec.in_score for spec in specs), "both L6 metrics must be in score")
    by_name = {spec.name: spec for spec in specs}
    _assert(
        by_name["RedundantCallRate"].producer.__name__ == "redundant_call_rate_det",
        "RedundantCallRate producer mismatch",
    )
    _assert(
        by_name["ToolAcc"].producer.__name__ != "redundant_call_rate_det",
        "ToolAcc must not use redundant_call_rate_det",
    )


def test_l7_spec_is_exactly_two_record_only_metrics():
    specs = level_spec.LEVEL_SPECS["L7"]
    _assert(len(specs) == 2, "L7 must have exactly two metric specs")
    _assert(
        tuple(spec.name for spec in specs)
        == ("ContextRetention_det", "RefRecall_det"),
        "L7 metric names mismatch",
    )
    _assert(
        all(spec.in_score is False for spec in specs),
        "both L7 metrics must remain record-only",
    )


def test_l6_empty_trace_depends_on_tool_acc():
    original_context = aggregate.build_eval_context
    original_specs = aggregate.LEVEL_SPECS["L6"]
    redundant_spec = next(
        spec for spec in original_specs if spec.name == "RedundantCallRate"
    )
    empty_context = DummyContext([], [])
    tasks = [{"resp_schema": {"type": "string"}} for _ in range(15)]

    def score_with_tool_acc(value):
        aggregate.LEVEL_SPECS["L6"] = (
            aggregate.MetricSpec("ToolAcc", lambda _ctx: value, True),
            redundant_spec,
        )
        return aggregate.score_level("L6", {"results": tasks})

    aggregate.build_eval_context = lambda _task: empty_context
    try:
        zero_result = score_with_tool_acc(0.0)
        _assert_close(zero_result["score"], 0.0, "zero-call ToolAcc zero score")
        redundant_entry = zero_result["metrics"]["RedundantCallRate"]
        _assert(
            redundant_entry["status"] == "not_applicable",
            "empty redundant call rate must be not applicable",
        )
        _assert(
            "unscorable_reason" not in zero_result,
            "ToolAcc keeps the empty-trace L6 level scorable",
        )

        one_result = score_with_tool_acc(1.0)
        # This documents the premise: if vendored ToolAcc ever rewards a 0-call
        # task, the original "everyone scores 100" inflation returns through this path.
        _assert_close(one_result["score"], 1.0, "zero-call ToolAcc rewarded score")
    finally:
        aggregate.build_eval_context = original_context
        aggregate.LEVEL_SPECS["L6"] = original_specs


def test_judge_missing_without_call():
    summary = aggregate.score_level("L7", {"results": []})
    entry = summary["metrics"]["SR"]
    _assert(entry["status"] == "judge_missing", "judge status mismatch")
    _assert(entry["score"] is None, "judge score should be None")
    _assert(entry["in_score"] is False, "judge in_score should be false")
    _assert(
        summary["unscorable_reason"] == "no_tasks",
        "empty L7 reason mismatch",
    )


def test_l7_without_ground_truth_is_all_not_applicable():
    summary = aggregate.score_level(
        "L7", {"results": [{"resp_schema": {"type": "string"}}]}
    )
    _assert(summary["score"] is None, "L7 score should be None")
    _assert(
        summary["unscorable_reason"] == "all_not_applicable",
        "L7 unscorable reason mismatch",
    )


def test_empty_level_spec_has_no_deterministic_metric_reason():
    original_specs = aggregate.LEVEL_SPECS["L1"]
    aggregate.LEVEL_SPECS["L1"] = ()
    try:
        result = aggregate.score_level(
            "L1", {"results": [{"resp_schema": {"type": "string"}}]}
        )
    finally:
        aggregate.LEVEL_SPECS["L1"] = original_specs
    _assert(
        result["unscorable_reason"] == "no_deterministic_metric",
        "empty metric spec reason mismatch",
    )


def test_missing_level_not_zero_filled():
    result = {
        "metadata": {"model": "x", "native_tool_calling": True, "success_rate": 100.0},
        "results": [],
    }
    summary = aggregate.build_summary_from_loaded(
        {"L7": result}, Path("/tmp/results/x/t/language/agent")
    )
    _assert("L1" in summary["levels_missing"], "missing L1 not recorded")
    _assert("L1" not in summary["by_level"], "missing L1 should not be zero-filled")
    _assert(summary["agent_score"] is None, "missing levels must not create score zero")


def test_non_l7_none_is_unscorable():
    summary = aggregate.build_summary_from_loaded(
        {"L1": {"results": []}}, Path("/tmp/results/x/t/language/agent")
    )
    _assert("L1" in summary["levels_unscorable"], "unscorable L1 not recorded")


def test_metric_error_fails_closed():
    original_context = aggregate.build_eval_context
    original_specs = aggregate.LEVEL_SPECS["L1"]

    def broken_metric(_ctx):
        raise RuntimeError("broken metric")

    aggregate.build_eval_context = lambda task: task
    aggregate.LEVEL_SPECS["L1"] = (
        aggregate.MetricSpec("Broken", broken_metric, True),
    )
    try:
        result = aggregate.score_level(
            "L1", {"results": [{"resp_schema": {"type": "string"}}]}
        )
    finally:
        aggregate.build_eval_context = original_context
        aggregate.LEVEL_SPECS["L1"] = original_specs

    _assert(result["metrics"]["Broken"]["status"] == "error", "error status lost")
    _assert(result["metrics"]["Broken"]["in_score"] is True, "in_score spec lost")
    _assert(result["score"] is None, "metric error must fail the level closed")
    _assert(
        result["unscorable_reason"] == "metric_error",
        "metric error reason mismatch",
    )


def test_partial_metric_keeps_level_scorable():
    original_context = aggregate.build_eval_context
    original_specs = aggregate.LEVEL_SPECS["L1"]

    def sometimes_broken(ctx):
        if ctx.get("broken"):
            raise ValueError("bad task")
        return ctx["score"]

    aggregate.build_eval_context = lambda task: task
    aggregate.LEVEL_SPECS["L1"] = (
        aggregate.MetricSpec("PartialMetric", sometimes_broken, True),
    )
    try:
        result = aggregate.score_level(
            "L1",
            {
                "results": [
                    {"score": 0.25, "resp_schema": {"type": "string"}},
                    {"broken": True, "resp_schema": {"type": "string"}},
                    {"score": 0.75, "resp_schema": {"type": "string"}},
                ]
            },
        )
    finally:
        aggregate.build_eval_context = original_context
        aggregate.LEVEL_SPECS["L1"] = original_specs

    entry = result["metrics"]["PartialMetric"]
    _assert(entry["status"] == "partial", "partial metric status mismatch")
    _assert(entry["n_tasks"] == 3, "partial metric task count mismatch")
    _assert(entry["n_scored"] == 2, "partial metric scored count mismatch")
    _assert(entry["n_errors"] == 1, "partial metric error count mismatch")
    _assert_close(entry["score"], 0.5, "partial metric mean")
    _assert_close(result["score"], 0.5, "partial metric level score")
    _assert(
        "unscorable_reason" not in result,
        "partial metric must not make the level unscorable",
    )

    summary = {
        "model": "x",
        "track": "agent",
        "agent_score": None,
        "agent_score_status": "incomplete",
        "scored_levels": 1,
        "required_levels": 6,
        "by_level": {"L1": result},
    }
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        score_run.print_table(summary, 5)
    _assert(
        "PartialMetric=0.500/partial(2/3)" in output.getvalue(),
        "partial metric coverage token mismatch",
    )


def test_all_tasks_error_fails_level_closed():
    original_context = aggregate.build_eval_context
    original_specs = aggregate.LEVEL_SPECS["L1"]

    def broken_metric(_ctx):
        raise RuntimeError("all broken")

    aggregate.build_eval_context = lambda task: task
    aggregate.LEVEL_SPECS["L1"] = (
        aggregate.MetricSpec("Broken", broken_metric, True),
    )
    try:
        result = aggregate.score_level(
            "L1",
            {
                "results": [
                    {"resp_schema": {"type": "string"}},
                    {"resp_schema": {"type": "string"}},
                    {"resp_schema": {"type": "string"}},
                ]
            },
        )
    finally:
        aggregate.build_eval_context = original_context
        aggregate.LEVEL_SPECS["L1"] = original_specs

    entry = result["metrics"]["Broken"]
    _assert(entry["status"] == "error", "all-error metric status mismatch")
    _assert(entry["n_tasks"] == 3, "all-error metric task count mismatch")
    _assert(entry["n_scored"] == 0, "all-error metric scored count mismatch")
    _assert(entry["n_errors"] == 3, "all-error metric error count mismatch")
    _assert(result["score"] is None, "all-error metric must fail level closed")
    _assert(
        result["unscorable_reason"] == "metric_error",
        "all-error unscorable reason mismatch",
    )


def test_record_only_metric_error_does_not_fail_level():
    original_context = aggregate.build_eval_context
    original_specs = aggregate.LEVEL_SPECS["L1"]

    def broken_metric(_ctx):
        raise RuntimeError("record only broken")

    aggregate.build_eval_context = lambda task: task
    aggregate.LEVEL_SPECS["L1"] = (
        aggregate.MetricSpec("Good", lambda _ctx: 0.75, True),
        aggregate.MetricSpec("RecordOnlyBroken", broken_metric, False),
    )
    try:
        result = aggregate.score_level(
            "L1", {"results": [{"resp_schema": {"type": "string"}}]}
        )
    finally:
        aggregate.build_eval_context = original_context
        aggregate.LEVEL_SPECS["L1"] = original_specs

    entry = result["metrics"]["RecordOnlyBroken"]
    _assert(entry["status"] == "error", "record-only error status mismatch")
    _assert(entry["in_score"] is False, "record-only in_score mismatch")
    _assert_close(result["score"], 0.75, "record-only error level score")


def test_all_in_score_metrics_not_applicable():
    original_context = aggregate.build_eval_context
    original_specs = aggregate.LEVEL_SPECS["L1"]
    aggregate.build_eval_context = lambda task: task
    aggregate.LEVEL_SPECS["L1"] = (
        aggregate.MetricSpec("NoScore", lambda _ctx: None, True),
    )
    try:
        result = aggregate.score_level(
            "L1", {"results": [{"resp_schema": {"type": "string"}}]}
        )
    finally:
        aggregate.build_eval_context = original_context
        aggregate.LEVEL_SPECS["L1"] = original_specs

    _assert(result["score"] is None, "all-not-applicable score must be None")
    _assert(
        result["unscorable_reason"] == "all_not_applicable",
        "all-not-applicable reason mismatch",
    )


def test_partial_run_is_incomplete():
    original = aggregate.score_level
    aggregate.score_level = lambda level, data: {
        "total": 1,
        "score": data["score"],
        "metrics": {},
    }
    try:
        summary = aggregate.build_summary_from_loaded(
            {"L1": {"score": 0.5}, "L3": {"score": 0.75}},
            Path("/tmp/results/x/t/language/agent"),
        )
    finally:
        aggregate.score_level = original

    _assert(summary["agent_score"] is None, "partial run must not have agent score")
    _assert(summary["scored_levels"] == 2, "partial scored level count mismatch")
    _assert(
        summary["agent_score_status"] == "incomplete",
        "partial run status mismatch",
    )


def test_complete_run_has_agent_score():
    original = aggregate.score_level
    aggregate.score_level = lambda level, data: {
        "total": 1,
        "score": data["score"],
        "metrics": {},
    }
    try:
        loaded = {
            level: {"score": index / 10.0}
            for index, level in enumerate(
                ("L1", "L2", "L3", "L4", "L5", "L6"), start=1
            )
        }
        summary = aggregate.build_summary_from_loaded(
            loaded, Path("/tmp/results/x/t/language/agent")
        )
    finally:
        aggregate.score_level = original

    _assert_close(summary["agent_score"], 0.35, "complete agent score")
    _assert(summary["scored_levels"] == 6, "complete scored level count mismatch")
    _assert(summary["required_levels"] == 6, "required level count mismatch")
    _assert(
        summary["agent_score_status"] == "complete",
        "complete run status mismatch",
    )


def test_scorable_levels_and_version_contract():
    _assert(
        aggregate.SCORABLE_LEVELS == ("L1", "L2", "L3", "L4", "L5", "L6"),
        "scorable levels contract mismatch",
    )
    _assert(
        aggregate.SCORING_VERSION == "agent_det_v2",
        "scoring version contract mismatch",
    )


def test_all_six_loaded_one_unscorable_is_incomplete():
    original = aggregate.score_level
    aggregate.score_level = lambda level, data: {
        "total": 1,
        "score": data["score"],
        "metrics": {},
    }
    try:
        loaded = {
            "L1": {"score": 0.1},
            "L2": {"score": 0.2},
            "L3": {"score": 0.3},
            "L4": {"score": None},
            "L5": {"score": 0.5},
            "L6": {"score": 0.6},
        }
        summary = aggregate.build_summary_from_loaded(
            loaded, Path("/tmp/results/x/t/language/agent")
        )
    finally:
        aggregate.score_level = original

    _assert(summary["agent_score"] is None, "one unscorable level must fail headline")
    _assert(summary["scored_levels"] == 5, "one-unscorable level count mismatch")
    _assert(
        summary["agent_score_status"] == "incomplete",
        "one-unscorable status mismatch",
    )


def test_complete_six_with_l7_ignores_l7_in_headline():
    original = aggregate.score_level
    aggregate.score_level = lambda level, data: {
        "total": 1,
        "score": data["score"],
        "metrics": {},
    }
    try:
        loaded = {
            "L1": {"score": 0.1},
            "L2": {"score": 0.2},
            "L3": {"score": 0.3},
            "L4": {"score": 0.4},
            "L5": {"score": 0.5},
            "L6": {"score": 0.6},
            "L7": {"score": None},
        }
        summary = aggregate.build_summary_from_loaded(
            loaded, Path("/tmp/results/x/t/language/agent")
        )
    finally:
        aggregate.score_level = original

    _assert_close(summary["agent_score"], 0.35, "L7-independent agent score")
    _assert("L7" in summary["levels_unscorable"], "L7 must be unscorable")
    _assert(summary["scored_levels"] == 6, "L7 must not affect scored level count")
    _assert(
        summary["agent_score_status"] == "complete",
        "L7 must not make headline incomplete",
    )


def test_empty_results_are_unscorable_no_tasks():
    summary = aggregate.build_summary_from_loaded(
        {"L2": {"results": [], "tasks": [{"ignored": True}]}},
        Path("/tmp/results/x/t/language/agent"),
    )
    result = summary["by_level"]["L2"]
    _assert(result["total"] == 0, "empty results must not fall through to tasks")
    _assert("L2" in summary["levels_unscorable"], "empty L2 not unscorable")
    _assert(result["unscorable_reason"] == "no_tasks", "no_tasks reason mismatch")


def test_print_table_shows_partial_run_status():
    summary = {
        "model": "x",
        "track": "agent",
        "agent_score": None,
        "agent_score_status": "incomplete",
        "scored_levels": 1,
        "required_levels": 6,
        "by_level": {
            "L1": {
                "total": 1,
                "score": None,
                "unscorable_reason": "all_not_applicable",
                "metrics": {},
            }
        },
    }
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        score_run.print_table(summary, 5)
    printed = output.getvalue()
    _assert("status=incomplete" in printed, "agent score status not printed")
    _assert("scored_levels=1/6" in printed, "scored level count not printed")
    _assert(
        "score=null unscorable=all_not_applicable" in printed,
        "unscorable level reason not printed",
    )


def test_print_table_shows_l7_record_only_metrics_without_judges():
    metrics = {
        "ContextRetention_det": {
            "score": 1.0,
            "status": "ok",
            "in_score": False,
        },
        "RefRecall_det": {"score": 0.5, "status": "ok", "in_score": False},
        "SR": {"score": None, "status": "judge_missing", "in_score": False},
        "ArgAcc": {"score": None, "status": "judge_missing", "in_score": False},
        "EffScore": {"score": None, "status": "judge_missing", "in_score": False},
        "ContextRetention": {
            "score": None,
            "status": "judge_missing",
            "in_score": False,
        },
        "RefRecall": {"score": None, "status": "judge_missing", "in_score": False},
    }
    summary = {
        "model": "x",
        "track": "agent",
        "agent_score": 0.5,
        "agent_score_status": "complete",
        "scored_levels": 6,
        "required_levels": 6,
        "by_level": {
            "L7": {
                "total": 1,
                "score": None,
                "unscorable_reason": "all_not_applicable",
                "metrics": metrics,
            }
        },
    }
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        score_run.print_table(summary, 0)
    printed = output.getvalue()
    _assert("ContextRetention_det=1.000/ok" in printed, "L7 context metric hidden")
    _assert("RefRecall_det=0.500/ok" in printed, "L7 recall metric hidden")
    _assert("judge_missing" not in printed, "judge-missing metrics must stay hidden")


def test_arg_f1_det_or_skip():
    base = os.environ.get("MODEL_TEST_BASE")
    metrics_py = Path(base or "") / "data" / "Ko-AgentBench" / "bench" / "runner" / "metrics.py"
    if not base or not metrics_py.is_file():
        print("SKIP test_arg_f1_det_or_skip: vendored Ko-AgentBench not available")
        return

    context = _load_module("context")
    task = {
        "task_id": "x",
        "golden_action": [{"tool": "A", "args": {"q": "x"}}],
        "arg_schema": {},
        "tool_calls": [
            {"tool_name": "A", "arguments": {"q": "x"}, "success": True, "error": None}
        ],
    }
    ctx = context.build_eval_context(task)
    _assert_close(extra_metrics.arg_f1_det(ctx), 1.0, "arg_f1_det")


TESTS = [
    test_fsm_prefix_exact_match,
    test_fsm_prefix_with_extra_calls,
    test_fsm_prefix_wrong_order,
    test_fsm_prefix_empty_golden,
    test_fsm_prefix_empty_actual,
    test_mean_excludes_none,
    test_mean_all_none,
    test_in_score_false_excluded,
    test_context_exposes_l7_ground_truth_with_empty_defaults,
    test_redundant_call_rate_empty_without_bench,
    test_redundant_call_rate_nonempty_loads_bench,
    test_context_retention_det_all_with_normalization_and_extra_args,
    test_context_retention_det_partial_and_wrong_value,
    test_context_retention_det_none_matched_and_no_data,
    test_ref_recall_det_all_and_partial,
    test_ref_recall_det_no_data_and_missing_tool_response,
    test_l6_spec_wires_redundant_call_rate,
    test_l7_spec_is_exactly_two_record_only_metrics,
    test_l6_empty_trace_depends_on_tool_acc,
    test_judge_missing_without_call,
    test_l7_without_ground_truth_is_all_not_applicable,
    test_empty_level_spec_has_no_deterministic_metric_reason,
    test_missing_level_not_zero_filled,
    test_non_l7_none_is_unscorable,
    test_metric_error_fails_closed,
    test_partial_metric_keeps_level_scorable,
    test_all_tasks_error_fails_level_closed,
    test_record_only_metric_error_does_not_fail_level,
    test_all_in_score_metrics_not_applicable,
    test_partial_run_is_incomplete,
    test_complete_run_has_agent_score,
    test_scorable_levels_and_version_contract,
    test_all_six_loaded_one_unscorable_is_incomplete,
    test_complete_six_with_l7_ignores_l7_in_headline,
    test_empty_results_are_unscorable_no_tasks,
    test_print_table_shows_partial_run_status,
    test_print_table_shows_l7_record_only_metrics_without_judges,
    test_arg_f1_det_or_skip,
]


def main():
    failures = []
    for test in TESTS:
        try:
            test()
        except AssertionError as exc:
            failures.append(f"{test.__name__}: {exc}")
        except Exception as exc:
            failures.append(f"{test.__name__}: unexpected {type(exc).__name__}: {exc}")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}", file=sys.stderr)
        return 1

    print(f"OK {len(TESTS)} cases")
    return 0


if __name__ == "__main__":
    sys.exit(main())
