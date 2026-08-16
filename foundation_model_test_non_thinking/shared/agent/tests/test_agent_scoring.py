"""agent scoring 단독 실행 테스트.

패키지 import 없이 파일 경로에서 직접 로드한다.
"""

import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
from pathlib import Path


SCORING_DIR = Path(__file__).resolve().parents[1] / "scoring"
CUSTOM_DIR = Path(__file__).resolve().parents[1] / "gpustack_custom"
TIMEOUT_CONFIG_PATH = (
    CUSTOM_DIR / "runner_timeout_config.py"
)
RESULT_OBSERVABILITY_PATH = CUSTOM_DIR / "result_observability.py"


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
validate_run = _load_module("validate_run")
scoring_context = _load_module("context")

_timeout_spec = importlib.util.spec_from_file_location(
    "runner_timeout_config_under_test", TIMEOUT_CONFIG_PATH
)
runner_timeout_config = importlib.util.module_from_spec(_timeout_spec)
_timeout_spec.loader.exec_module(runner_timeout_config)

_result_spec = importlib.util.spec_from_file_location(
    "result_observability_under_test", RESULT_OBSERVABILITY_PATH
)
result_observability = importlib.util.module_from_spec(_result_spec)
_result_spec.loader.exec_module(result_observability)


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


def test_runner_request_timeout_parse_default_and_override():
    defaults = runner_timeout_config.parse_args([])
    overridden = runner_timeout_config.parse_args(["--request-timeout", "300"])
    _assert(defaults.request_timeout == 60, "request timeout default must be 60")
    _assert(overridden.request_timeout == 300, "request timeout flag was ignored")


def test_runner_max_retries_parse_default_and_override():
    defaults = runner_timeout_config.parse_args([])
    overridden = runner_timeout_config.parse_args(["--max-retries", "4"])
    _assert(defaults.max_retries == 2, "max retries default must be 2")
    _assert(overridden.max_retries == 4, "max retries flag was ignored")


def test_runner_adapter_config_contains_request_timeout():
    # adapter_config 는 "request_timeout" 키로 나른다. "timeout" 을 쓰면
    # run_benchmark_on_dataset(timeout=태스크예산) 의 명명 인자와 충돌해
    # TypeError: got multiple values for keyword argument 'timeout' 이 난다.
    args = runner_timeout_config.parse_args(["--request-timeout", "300"])
    config = runner_timeout_config.build_adapter_config(args)
    _assert(config.get("request_timeout") == 300, "adapter timeout plumbing mismatch")
    _assert("timeout" not in config, "adapter_config must not carry a 'timeout' key")


def test_runner_adapter_config_maps_to_adapter_timeout():
    # 러너가 어댑터 생성 직전에 하는 변환을 그대로 재현한다.
    args = runner_timeout_config.parse_args(["--request-timeout", "250"])
    config = dict(runner_timeout_config.build_adapter_config(args))
    if "request_timeout" in config:
        config["timeout"] = config.pop("request_timeout")
    _assert(config.get("timeout") == 250, "request_timeout must map to adapter timeout")


def test_runner_timeout_guard_rejects_non_greater_task_budget():
    for task_timeout in (299, 300):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            rc = runner_timeout_config.main(
                ["--timeout", str(task_timeout), "--request-timeout", "300"]
            )
        _assert(rc != 0, "non-greater task/request timeouts must fail")
        _assert(stderr.getvalue().startswith("[ERROR] "), "guard error prefix mismatch")


def test_runner_timeout_guard_accepts_greater_task_budget():
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        rc = runner_timeout_config.main(
            ["--timeout", "301", "--request-timeout", "300"]
        )
    _assert(rc == 0, "greater task timeout must be accepted")


def test_result_observability_builders():
    raw_result = {
        "ttft_stats": {"average": 1.5, "min": 1.0, "max": 2.0, "count": 2},
        "result": {
            "steps": [
                {"llm_response": {"finish_reason": "length"}},
                {"llm_response": {"finish_reason": "stop"}},
            ]
        },
    }
    task_fields = {
        "completion_latency": result_observability.completion_latency_from_task(raw_result),
        **result_observability.finish_reason_fields(raw_result),
    }
    metadata = result_observability.build_observability_metadata([task_fields])

    _assert("completion_latency" in metadata, "completion latency metadata missing")
    _assert("ttft" not in metadata, "new metadata must not emit the old ttft key")
    _assert(task_fields["last_finish_reason"] == "stop", "last finish reason mismatch")
    _assert(
        isinstance(task_fields["length_finish_reason_count"], int),
        "per-task truncation count must be an integer",
    )
    _assert(task_fields["length_finish_reason_count"] == 1, "length finish count mismatch")
    _assert(
        isinstance(metadata["tasks_with_length_finish_reason"], int),
        "level truncation count must be an integer",
    )
    _assert(metadata["tasks_with_length_finish_reason"] == 1, "truncated task count mismatch")


def test_old_ttft_summary_reader_does_not_crash():
    old_summary = {
        "metadata": {
            "ttft": {"average": 3.0, "min": 2.0, "max": 4.0, "unit": "seconds"}
        }
    }
    latency = result_observability.read_completion_latency(old_summary)
    _assert(latency["average"] == 3.0, "legacy ttft compatibility read mismatch")


def _task_spread(score):
    return {
        "n_perfect": int(score == 1.0),
        "n_zero": int(score == 0.0),
        "n_partial": int(0.0 < score < 1.0),
    }


def _validation_summary():
    by_level = {}
    for index, level in enumerate(aggregate.ALL_LEVELS, start=1):
        level_value = index / 10.0 if level != "L7" else None
        metrics = {}
        for metric_spec in level_spec.LEVEL_SPECS[level]:
            metric_value = level_value if level_value is not None else 0.5
            metrics[metric_spec.name] = {
                "score": metric_value,
                "status": "ok",
                "in_score": metric_spec.in_score,
                "n_tasks": 1,
                "n_scored": 1,
                "n_errors": 0,
                "task_spread": _task_spread(metric_value),
            }
        for metric_name in level_spec.JUDGE_METRICS:
            metrics[metric_name] = {
                "score": None,
                "status": "judge_missing",
                "in_score": False,
            }
        by_level[level] = {
            "total": 1,
            "score": level_value,
            "applied_metrics": sum(
                entry["in_score"] and entry["status"] in {"ok", "partial"}
                for entry in metrics.values()
            ),
            "metrics": metrics,
        }
    return {
        "benchmark": "Ko-AgentBench (deterministic scoring)",
        "model": "test_model",
        "track": "agent_test",
        "scoring_version": aggregate.SCORING_VERSION,
        "native_tool_calling": True,
        "agent_score": 0.35,
        "scored_levels": 6,
        "required_levels": 6,
        "agent_score_status": "complete",
        "by_level": by_level,
    }


def _write_validation_fixture(results_dir, summary, native_overrides=None):
    native_overrides = native_overrides or {}
    (results_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    for level in summary.get("by_level", {}):
        metadata = {
            "success_rate": 0.5,
        }
        native = native_overrides.get(level, True)
        if native is not None:
            metadata["native_tool_calling"] = native
        raw = {
            "metadata": metadata,
            "results": [{}],
        }
        (results_dir / f"{level}.json").write_text(json.dumps(raw), encoding="utf-8")


def _validate_fixture(summary, native_overrides=None):
    with tempfile.TemporaryDirectory() as temp_dir:
        results_dir = Path(temp_dir)
        _write_validation_fixture(results_dir, summary, native_overrides)
        return validate_run.validate_results_dir(results_dir)


def _validator_exit(argv):
    with contextlib.redirect_stdout(io.StringIO()):
        return validate_run.main(argv)


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


def _result_field_coverage_context(final_response, golden_fields=None, include_second=True):
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


def _single_result_field_context(value, final_response, field_name="value"):
    result = {"value": value}
    return DummyContext(
        action_trace=[{"tool": "Lookup", "args": {}, "result": result}],
        task_schema={
            "golden_fields": [{"tool": "Lookup", "fields": [field_name]}]
        },
        logs={
            "conversation_log": {
                "messages": [
                    {"role": "tool", "tool_call_id": "call_1", "content": result}
                ]
            },
            "final_response": final_response,
        },
    )


def test_result_field_coverage_all_and_partial():
    all_present = _result_field_coverage_context(
        "The price is 1,234 and the title is ALPHA BOOK by beta writer."
    )
    _assert_close(
        extra_metrics.result_field_coverage_det(all_present),
        1.0,
        "all result fields covered",
    )

    one_missing = _result_field_coverage_context(
        "The price is 1234.0; title: alpha book."
    )
    _assert_close(
        extra_metrics.result_field_coverage_det(one_missing),
        0.5,
        "one result entry missing",
    )


def test_result_field_coverage_numeric_tolerance():
    ctx = _single_result_field_context(1.9782121400000001, "약 1.98% 상승")
    _assert_close(
        extra_metrics.result_field_coverage_det(ctx), 1.0, "model precision"
    )


def test_result_field_coverage_thousands_separator():
    ctx = _single_result_field_context(129650000.0, "129,650,000원")
    _assert_close(
        extra_metrics.result_field_coverage_det(ctx), 1.0, "thousands separator"
    )


def test_result_field_coverage_wrong_number():
    ctx = _single_result_field_context(129650000.0, "131,000,000원")
    _assert_close(extra_metrics.result_field_coverage_det(ctx), 0.0, "wrong number")


def test_result_field_coverage_normalizes_string_html_and_case():
    ctx = _single_result_field_context("<b>Alpha</b>   BOOK", "alpha book is available")
    _assert_close(
        extra_metrics.result_field_coverage_det(ctx), 1.0, "normalized string"
    )


def test_result_field_coverage_excludes_long_text():
    long_text = "This is a long result description " * 4
    ctx = _single_result_field_context(long_text, "short summary")
    _assert(
        extra_metrics.result_field_coverage_det(ctx) is None,
        "all-long-text task must yield no judgement",
    )
    diagnostics = extra_metrics.result_field_coverage_diagnostics(ctx)
    _assert(diagnostics["fields_required"] == 1, "long field required count")
    _assert(diagnostics["fields_checked"] == 0, "long field checked count")
    _assert(
        diagnostics["fields_excluded_long_text"] == 1,
        "long field exclusion count",
    )
    _assert(diagnostics["fields_unresolved"] == 0, "long field unresolved count")


def test_result_field_coverage_counts_unresolved_as_failure():
    ctx = _single_result_field_context("present", "present", "missing.path")
    _assert_close(
        extra_metrics.result_field_coverage_det(ctx), 0.0, "unresolved field"
    )
    diagnostics = extra_metrics.result_field_coverage_diagnostics(ctx)
    _assert(diagnostics["fields_required"] == 1, "unresolved required count")
    _assert(diagnostics["fields_checked"] == 0, "unresolved checked count")
    _assert(
        diagnostics["fields_excluded_long_text"] == 0,
        "unresolved exclusion count",
    )
    _assert(diagnostics["fields_unresolved"] == 1, "unresolved field count")


def test_result_field_coverage_no_data_and_missing_tool_response():
    no_data = _result_field_coverage_context("anything", golden_fields=[])
    _assert(
        extra_metrics.result_field_coverage_det(no_data) is None,
        "no golden fields must be not applicable",
    )

    missing_response = _single_result_field_context("present", "present")
    missing_response.action_trace = []
    missing_response.logs["conversation_log"] = {"messages": []}
    _assert(
        extra_metrics.result_field_coverage_det(missing_response) is None,
        "missing tool response must be not applicable",
    )
    diagnostics = extra_metrics.result_field_coverage_diagnostics(missing_response)
    _assert(diagnostics["fields_required"] == 1, "missing-response required count")
    _assert(diagnostics["fields_checked"] == 0, "missing-response checked count")
    _assert(diagnostics["fields_unresolved"] == 0, "missing response is not unresolved")


def test_result_field_coverage_diagnostics_are_aggregated():
    original_context = aggregate.build_eval_context
    ctx = _single_result_field_context("present", "present")
    spec = next(
        spec
        for spec in level_spec.LEVEL_SPECS["L7"]
        if spec.name == "ResultFieldCoverage_det"
    )
    aggregate.build_eval_context = lambda _task: ctx
    try:
        entry = aggregate._average_metric([{}, {}], spec)
    finally:
        aggregate.build_eval_context = original_context
    _assert(entry["fields_required"] == 2, "aggregate required count")
    _assert(entry["fields_checked"] == 2, "aggregate checked count")
    _assert(entry["fields_excluded_long_text"] == 0, "aggregate excluded count")
    _assert(entry["fields_unresolved"] == 0, "aggregate unresolved count")


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
        == ("ContextRetention_det", "ResultFieldCoverage_det"),
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


def test_legacy_missing_native_tool_calling_defaults_false():
    original = aggregate.score_level
    aggregate.score_level = lambda level, data: {
        "total": 1,
        "score": data["score"],
        "metrics": {},
    }
    try:
        summary = aggregate.build_summary_from_loaded(
            {"L1": {"score": 0.5}},
            Path("/tmp/results/x/t/language/agent"),
        )
    finally:
        aggregate.score_level = original

    _assert(
        summary["native_tool_calling"] is False,
        "legacy result without native metadata must default false",
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
        "ResultFieldCoverage_det": {
            "score": 0.5,
            "status": "ok",
            "in_score": False,
            "n_scored": 3,
            "n_tasks": 10,
        },
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
    _assert(
        "ResultFieldCoverage_det=0.500/ok(3/10)" in printed,
        "L7 result field metric or scored-task count hidden",
    )
    _assert("judge_missing" not in printed, "judge-missing metrics must stay hidden")


def test_task_spread_counts_scored_tasks():
    original_context = aggregate.build_eval_context
    aggregate.build_eval_context = lambda task: task
    try:
        entry = aggregate._average_metric(
            [{"score": 1.0}, {"score": 0.0}, {"score": 0.25}],
            aggregate.MetricSpec("Spread", lambda task: task["score"], True),
        )
    finally:
        aggregate.build_eval_context = original_context
    _assert(
        entry["task_spread"]
        == {"n_perfect": 1, "n_zero": 1, "n_partial": 1},
        "task spread buckets mismatch",
    )
    _assert(
        sum(entry["task_spread"].values()) == entry["n_scored"],
        "task spread must sum to n_scored",
    )


def test_applied_metrics_counts_only_scored_in_score_metrics():
    original_context = aggregate.build_eval_context
    original_specs = aggregate.LEVEL_SPECS["L6"]
    aggregate.build_eval_context = lambda task: task
    aggregate.LEVEL_SPECS["L6"] = (
        aggregate.MetricSpec("Applied", lambda _task: 0.5, True),
        aggregate.MetricSpec("Missing", lambda _task: None, True),
    )
    try:
        result = aggregate.score_level("L6", {"results": [{}]})
        output = io.StringIO()
        summary = {
            "model": "x",
            "track": "agent",
            "agent_score": None,
            "agent_score_status": "incomplete",
            "scored_levels": 1,
            "required_levels": 6,
            "by_level": {"L6": result},
        }
        with contextlib.redirect_stdout(output):
            score_run.print_table(summary, 5)
    finally:
        aggregate.build_eval_context = original_context
        aggregate.LEVEL_SPECS["L6"] = original_specs
    _assert(result["applied_metrics"] == 1, "applied metric count mismatch")
    _assert(
        "applied_metrics=1/2" in output.getvalue(),
        "reduced applied metric count not printed",
    )


def test_validator_accepts_complete_summary():
    failures, _warnings = _validate_fixture(_validation_summary())
    _assert(not failures, f"complete summary failed validation: {failures}")


def test_validator_main_nonexistent_results_dir_exits_2():
    with tempfile.TemporaryDirectory() as temp_dir:
        missing = Path(temp_dir) / "missing"
        exit_code = _validator_exit(["--results-dir", str(missing)])
    _assert(exit_code == 2, f"nonexistent results dir exited {exit_code}, expected 2")


def test_validator_main_missing_summary_exits_1():
    with tempfile.TemporaryDirectory() as temp_dir:
        exit_code = _validator_exit(["--results-dir", temp_dir])
    _assert(exit_code == 1, f"missing summary exited {exit_code}, expected 1")


def test_validator_main_complete_summary_exits_0():
    with tempfile.TemporaryDirectory() as temp_dir:
        results_dir = Path(temp_dir)
        _write_validation_fixture(results_dir, _validation_summary())
        exit_code = _validator_exit(["--results-dir", str(results_dir)])
    _assert(exit_code == 0, f"complete summary exited {exit_code}, expected 0")


def test_validator_main_unparseable_summary_exits_2():
    with tempfile.TemporaryDirectory() as temp_dir:
        results_dir = Path(temp_dir)
        (results_dir / "summary.json").write_text("{", encoding="utf-8")
        exit_code = _validator_exit(["--results-dir", str(results_dir)])
    _assert(exit_code == 2, f"unparseable summary exited {exit_code}, expected 2")


def test_validator_accepts_partial_summary():
    summary = _validation_summary()
    del summary["by_level"]["L6"]
    summary["agent_score"] = None
    summary["agent_score_status"] = "incomplete"
    summary["scored_levels"] = 5
    failures, _warnings = _validate_fixture(summary)
    _assert(not failures, f"partial summary failed validation: {failures}")


def test_validator_accepts_legacy_missing_native_metadata():
    summary = _validation_summary()
    summary["native_tool_calling"] = False
    native_overrides = {level: None for level in summary["by_level"]}
    failures, warnings = _validate_fixture(summary, native_overrides)
    _assert(not failures, f"legacy native metadata failed validation: {failures}")
    _assert(
        len([warning for warning in warnings if "treating legacy run as false" in warning])
        == len(summary["by_level"]),
        "legacy native metadata warnings mismatch",
    )


def test_validator_rejects_version_mismatch():
    summary = _validation_summary()
    summary["scoring_version"] = "agent_det_old"
    failures, _warnings = _validate_fixture(summary)
    _assert(any("scoring_version mismatch" in item for item in failures), "version mismatch passed")


def test_validator_rejects_score_outside_unit_interval():
    summary = _validation_summary()
    summary["by_level"]["L1"]["metrics"]["ToolAcc"]["score"] = 1.01
    failures, _warnings = _validate_fixture(summary)
    _assert(any("within [0, 1]" in item for item in failures), "out-of-range score passed")


def test_validator_rejects_partial_in_score_metric():
    summary = _validation_summary()
    summary["by_level"]["L1"]["metrics"]["ToolAcc"]["status"] = "partial"
    failures, _warnings = _validate_fixture(summary)
    _assert(any("unclean status" in item for item in failures), "partial metric passed")


def test_validator_rejects_not_applicable_numeric_score():
    summary = _validation_summary()
    summary["by_level"]["L1"]["metrics"]["pass@k"] = {
        "score": 0.0,
        "status": "not_applicable",
        "in_score": False,
    }
    failures, _warnings = _validate_fixture(summary)
    _assert(
        any("must not carry a numeric score" in item for item in failures),
        "not-applicable numeric score passed",
    )


def test_validator_rejects_native_tool_calling_disagreement():
    failures, _warnings = _validate_fixture(
        _validation_summary(), {"L1": True, "L2": False}
    )
    _assert(
        any("disagrees across raw levels" in item for item in failures),
        "native tool calling disagreement passed",
    )


def test_validator_rejects_headline_status_mismatch_both_directions():
    incomplete = _validation_summary()
    incomplete["agent_score_status"] = "incomplete"
    failures, _warnings = _validate_fixture(incomplete)
    _assert(
        any("if and only if status is complete" in item for item in failures),
        "headline present with incomplete status passed",
    )

    complete_without_score = _validation_summary()
    complete_without_score["agent_score"] = None
    failures, _warnings = _validate_fixture(complete_without_score)
    _assert(
        any("if and only if status is complete" in item for item in failures),
        "headline missing with complete status passed",
    )


def test_validator_rejects_perturbed_agent_score():
    summary = _validation_summary()
    summary["agent_score"] += 0.001
    failures, _warnings = _validate_fixture(summary)
    _assert(any("mean invariant failed" in item for item in failures), "perturbed mean passed")


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


def _runner_source():
    return (CUSTOM_DIR / "run_gpustack_benchmark_with_logging.py").read_text()


def _timeout_config_source():
    return TIMEOUT_CONFIG_PATH.read_text()


def _adapter_source():
    return (CUSTOM_DIR / "openai_compat_adapter.py").read_text()


def test_runner_passes_max_retries_to_benchmark_runner():
    import ast

    runner = ast.parse(_runner_source())
    calls = [
        node for node in ast.walk(runner)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "BenchmarkRunner"
    ]
    _assert(calls, "BenchmarkRunner construction disappeared")
    keyword = next(
        (kw for kw in calls[0].keywords if kw.arg == "max_retries"),
        None,
    )
    _assert(keyword is not None, "BenchmarkRunner does not receive max_retries")
    _assert(
        isinstance(keyword.value, ast.Name) and keyword.value.id == "max_retries",
        "BenchmarkRunner must receive the run_benchmark_on_dataset max_retries argument",
    )

    run_calls = [
        node for node in ast.walk(runner)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "run_benchmark_on_dataset"
    ]
    _assert(run_calls, "run_benchmark_on_dataset call disappeared")
    run_keyword = next(
        (kw for kw in run_calls[0].keywords if kw.arg == "max_retries"),
        None,
    )
    _assert(run_keyword is not None, "CLI max_retries is not passed to the dataset runner")
    _assert(
        isinstance(run_keyword.value, ast.Attribute)
        and isinstance(run_keyword.value.value, ast.Name)
        and run_keyword.value.value.id == "args"
        and run_keyword.value.attr == "max_retries",
        "dataset runner must receive args.max_retries",
    )


def test_adapter_disables_openai_sdk_retries():
    import ast

    adapter = ast.parse(_adapter_source())
    calls = [
        node for node in ast.walk(adapter)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "OpenAI"
    ]
    _assert(calls, "OpenAI client construction disappeared")
    retry_keywords = [
        kw for call in calls for kw in call.keywords if kw.arg == "max_retries"
    ]
    _assert(retry_keywords, "OpenAI client no longer sets max_retries explicitly")
    _assert(
        all(isinstance(kw.value, ast.Constant) and kw.value.value == 0
            for kw in retry_keywords),
        "OpenAI SDK max_retries must be the literal 0",
    )


def test_adapter_config_keys_do_not_collide_with_call_site():
    """adapter_config 키가 run_benchmark_on_dataset 의 명명 인자와 겹치면 안 된다.

    겹치면 `f(timeout=..., **adapter_config)` 가
    TypeError: got multiple values for keyword argument 'timeout' 로 죽는다.
    러너는 vendored bench 없이 import 되지 않아 단위 테스트로 못 덮는 구간이라
    소스를 AST 로 정적 검사한다.
    """
    import ast

    runner = ast.parse(_runner_source())
    fn = next(
        (n for n in ast.walk(runner)
         if isinstance(n, ast.FunctionDef) and n.name == "run_benchmark_on_dataset"),
        None,
    )
    _assert(fn is not None, "run_benchmark_on_dataset 를 찾지 못했다")
    params = {a.arg for a in fn.args.args} | {a.arg for a in fn.args.kwonlyargs}

    cfg = ast.parse(_timeout_config_source())
    build = next(
        (n for n in ast.walk(cfg)
         if isinstance(n, ast.FunctionDef) and n.name == "build_adapter_config"),
        None,
    )
    _assert(build is not None, "build_adapter_config 를 찾지 못했다")

    keys = set()
    for node in ast.walk(build):
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if (isinstance(tgt, ast.Subscript)
                        and isinstance(tgt.value, ast.Name)
                        and tgt.value.id == "adapter_config"
                        and isinstance(tgt.slice, ast.Constant)):
                    keys.add(tgt.slice.value)

    _assert(keys, "build_adapter_config 에서 키를 하나도 못 찾았다 — 검사가 무력화됐다")
    clash = keys & params
    _assert(not clash, f"adapter_config 키가 호출부 인자와 충돌: {sorted(clash)}")


TESTS = [
    test_runner_request_timeout_parse_default_and_override,
    test_runner_max_retries_parse_default_and_override,
    test_runner_adapter_config_contains_request_timeout,
    test_runner_adapter_config_maps_to_adapter_timeout,
    test_runner_passes_max_retries_to_benchmark_runner,
    test_adapter_disables_openai_sdk_retries,
    test_adapter_config_keys_do_not_collide_with_call_site,
    test_runner_timeout_guard_rejects_non_greater_task_budget,
    test_runner_timeout_guard_accepts_greater_task_budget,
    test_result_observability_builders,
    test_old_ttft_summary_reader_does_not_crash,
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
    test_result_field_coverage_all_and_partial,
    test_result_field_coverage_numeric_tolerance,
    test_result_field_coverage_thousands_separator,
    test_result_field_coverage_wrong_number,
    test_result_field_coverage_normalizes_string_html_and_case,
    test_result_field_coverage_excludes_long_text,
    test_result_field_coverage_counts_unresolved_as_failure,
    test_result_field_coverage_no_data_and_missing_tool_response,
    test_result_field_coverage_diagnostics_are_aggregated,
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
    test_legacy_missing_native_tool_calling_defaults_false,
    test_complete_run_has_agent_score,
    test_scorable_levels_and_version_contract,
    test_all_six_loaded_one_unscorable_is_incomplete,
    test_complete_six_with_l7_ignores_l7_in_headline,
    test_empty_results_are_unscorable_no_tasks,
    test_print_table_shows_partial_run_status,
    test_print_table_shows_l7_record_only_metrics_without_judges,
    test_task_spread_counts_scored_tasks,
    test_applied_metrics_counts_only_scored_in_score_metrics,
    test_validator_accepts_complete_summary,
    test_validator_main_nonexistent_results_dir_exits_2,
    test_validator_main_missing_summary_exits_1,
    test_validator_main_complete_summary_exits_0,
    test_validator_main_unparseable_summary_exits_2,
    test_validator_accepts_partial_summary,
    test_validator_accepts_legacy_missing_native_metadata,
    test_validator_rejects_version_mismatch,
    test_validator_rejects_score_outside_unit_interval,
    test_validator_rejects_partial_in_score_metric,
    test_validator_rejects_not_applicable_numeric_score,
    test_validator_rejects_native_tool_calling_disagreement,
    test_validator_rejects_headline_status_mismatch_both_directions,
    test_validator_rejects_perturbed_agent_score,
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
