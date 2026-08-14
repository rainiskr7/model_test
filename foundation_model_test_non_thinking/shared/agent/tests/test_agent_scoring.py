"""agent scoring 단독 실행 테스트.

패키지 import 없이 파일 경로에서 직접 로드한다.
"""

import importlib.util
import os
import sys
from pathlib import Path


SCORING_DIR = Path(__file__).resolve().parents[1] / "scoring"
TREE_ROOT = Path(__file__).resolve().parents[3]
if not os.environ.get("MODEL_TEST_BASE") and (
    TREE_ROOT / "data" / "Ko-AgentBench" / "bench" / "runner" / "metrics.py"
).is_file():
    os.environ["MODEL_TEST_BASE"] = str(TREE_ROOT)


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
score_run = _load_module("score_run")
context = _load_module("context")


class DummyContext:
    def __init__(self, golden_action, action_trace, minimum_calls=None):
        self.task_schema = {"golden_action": golden_action}
        if minimum_calls is not None:
            self.task_schema["minimum_calls"] = minimum_calls
        self.action_trace = action_trace


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


def test_judge_missing_without_call():
    summary = score_run.score_level("L7", {"results": []})
    entry = summary["metrics"]["SR"]
    _assert(entry["status"] == "judge_missing", "judge status mismatch")
    _assert(entry["score"] is None, "judge score should be None")
    _assert(entry["in_score"] is False, "judge in_score should be false")


def test_missing_level_not_zero_filled():
    result = {
        "metadata": {"model": "x", "native_tool_calling": True, "success_rate": 100.0},
        "results": [],
    }
    summary = score_run.build_summary_from_loaded_for_test(
        {"L7": result},
        Path("/tmp/results/x/t/language/agent"),
        bench_task_maps={},
        bench_pin_value={"tasks_sha256": {}},
    )
    _assert("L1" in summary["levels_missing"], "missing L1 not recorded")
    _assert("L1" not in summary["by_level"], "missing L1 should not be zero-filled")
    _assert(summary["agent_score"] is None, "missing levels must not create score zero")


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


def test_l6_empty_tool_calls_not_full_score():
    task = {
        "task_id": "L6-x",
        "level": 6,
        "golden_action": [
            {"tool": "A", "args": {"q": "x"}},
            {"action": "context_used"},
            {"tool": "B", "args": {"q": "x"}},
        ],
        "tool_calls": [],
    }
    bench_task = {
        "task_id": "L6-x",
        "golden_action": task["golden_action"],
        "minimum_calls": 2,
    }
    ctx = context.build_eval_context(task, bench_task)
    _assert_close(extra_metrics.call_eff_det(ctx), 0.0, "empty calls call_eff_det")

    summary = score_run.score_level("L6", {"results": [task]}, {"L6-x": bench_task})
    _assert_close(summary["metrics"]["CallEff_det"]["score"], 0.0, "L6 CallEff_det")
    _assert_close(summary["metrics"]["ToolAcc"]["score"], 0.0, "L6 ToolAcc")
    _assert_close(summary["metrics"]["Coverage"]["score"], 0.0, "L6 Coverage")
    _assert(summary["score"] != 1.0, "L6 representative score must not be full")
    _assert_close(summary["score"], 0.0, "L6 representative score")


def _l7_bench_task(context_tests):
    return {
        "task_id": "L7-x",
        "task_level": 7,
        "conversation_tracking": {
            "evaluation_context": {
                "context_tests": context_tests,
            }
        },
    }


def test_l7_expected_action_synthesized_and_scored():
    expected = {"tool": "CryptoPrice_upbit", "args": {"symbol": "BTC", "quote": "KRW"}}
    task = {
        "task_id": "L7-x",
        "level": 7,
        "golden_action": [],
        "arg_schema": {},
        "tool_calls": [
            {
                "tool_name": "CryptoPrice_upbit",
                "arguments": {"symbol": "BTC", "quote": "KRW"},
                "success": True,
            }
        ],
    }
    bench_task = _l7_bench_task([{"expected_action": expected}])
    task_schema, _ = context.task_to_schema_and_logs(task, bench_task)
    _assert(task_schema.get("_golden_action_synthesized") is True, "L7 synth marker")
    _assert(task_schema["golden_action"] == [expected], "L7 expected_action synthesized")

    summary = score_run.score_level("L7", {"results": [task]}, {"L7-x": bench_task})
    _assert_close(summary["metrics"]["ToolAcc"]["score"], 1.0, "L7 ToolAcc")
    _assert_close(summary["metrics"]["CallEM"]["score"], 1.0, "L7 CallEM")
    _assert_close(summary["metrics"]["ArgF1_det"]["score"], 1.0, "L7 ArgF1_det")


def test_l7_context_test_without_expected_action_skipped():
    expected = {"tool": "A", "args": {"x": 1}}
    task = {"task_id": "L7-x", "level": 7, "golden_action": [], "tool_calls": []}
    bench_task = _l7_bench_task([
        {"name": "retention_only"},
        {"expected_action": expected},
    ])
    task_schema, _ = context.task_to_schema_and_logs(task, bench_task)
    _assert(task_schema["golden_action"] == [expected], "skip non-action context tests")


def test_golden_action_drift_records_error_not_zero():
    task = {
        "task_id": "L7-x",
        "level": 7,
        "golden_action": [{"tool": "A", "args": {}}],
        "tool_calls": [{"tool_name": "A", "arguments": {}, "success": True}],
    }
    bench_task = {"task_id": "L7-x", "golden_action": [{"tool": "B", "args": {}}]}
    summary = score_run.score_level("L7", {"results": [task]}, {"L7-x": bench_task})
    entry = summary["metrics"]["ToolAcc"]
    _assert(entry["status"] == "error", "drift should be error")
    _assert(entry["score"] is None, "drift score should be None")
    _assert(summary["score"] is None, "drift level score should be None")


def test_bench_task_none_keeps_existing_behavior():
    task = {
        "task_id": "x",
        "instruction": "do it",
        "level": 1,
        "category": "cat",
        "golden_action": [{"tool": "A", "args": {}}],
        "tool_calls": [{"tool_name": "A", "arguments": {}, "success": True}],
    }
    before = context.task_to_schema_and_logs(task)
    after = context.task_to_schema_and_logs(task, None)
    _assert(before == after, "bench_task=None must be unchanged")


def test_repetition_records_average_metric_entry():
    task = {
        "task_id": "L1-repeat",
        "level": 1,
        "golden_action": [{"tool": "A", "args": {"q": "x"}}],
        "tool_calls": [{"tool_name": "B", "arguments": {"q": "x"}, "success": True}],
        "repetitions": 2,
        "repetition_results": [True, True],
        "repetition_records": [
            {
                "rep_index": 0,
                "success": True,
                "tool_calls": [{"tool_name": "A", "arguments": {"q": "x"}, "success": True}],
            },
            {
                "rep_index": 1,
                "success": True,
                "tool_calls": [{"tool_name": "B", "arguments": {"q": "x"}, "success": True}],
            },
        ],
    }
    bench_task = {"task_id": "L1-repeat", "golden_action": task["golden_action"]}
    summary = score_run.score_level("L1", {"results": [task]}, {"L1-repeat": bench_task})
    entry = summary["metrics"]["CallEM"]
    _assert_close(entry["score"], 0.5, "CallEM repeated average")
    _assert(entry["repeated"] is True, "repeated flag")
    _assert(entry["n_repetitions"] == 2, "n_repetitions")
    _assert_close(entry["std"], 0.5, "population std")
    _assert(entry["per_repetition"] == [1.0, 0.0], "per repetition scores")


def test_no_repetition_records_keeps_metric_entry_shape():
    task = {
        "task_id": "L1-single",
        "level": 1,
        "golden_action": [{"tool": "A", "args": {}}],
        "tool_calls": [{"tool_name": "A", "arguments": {}, "success": True}],
    }
    bench_task = {"task_id": "L1-single", "golden_action": task["golden_action"]}
    summary = score_run.score_level("L1", {"results": [task]}, {"L1-single": bench_task})
    entry = summary["metrics"]["CallEM"]
    _assert_close(entry["score"], 1.0, "single CallEM")
    for key in ("repeated", "n_repetitions", "std", "per_repetition"):
        _assert(key not in entry, f"{key} must not appear without repetition_records")


def test_passk_det_passes_if_one_repetition_primary_is_full():
    records = []
    for index in range(5):
        tool = "A" if index == 3 else "B"
        records.append({
            "rep_index": index,
            "success": True,
            "tool_calls": [{"tool_name": tool, "arguments": {}, "success": True}],
        })
    task = {
        "task_id": "L2-passk",
        "level": 2,
        "golden_action": [{"tool": "A", "args": {}}],
        "tool_calls": [],
        "repetitions": 5,
        "repetition_results": [True] * 5,
        "repetition_records": records,
    }
    bench_task = {"task_id": "L2-passk", "golden_action": task["golden_action"]}
    summary = score_run.score_level("L2", {"results": [task]}, {"L2-passk": bench_task})
    entry = summary["metrics"]["PassK_det"]
    _assert_close(entry["score"], 1.0, "PassK_det one full repetition passes")
    _assert(entry["primary_metric"] == "SelectAcc", "L2 primary")
    _assert(entry["k"] == 5, "PassK_det k")


def test_passk_det_not_in_representative_score():
    records = []
    for index in range(5):
        tool = "A" if index == 0 else "B"
        records.append({
            "rep_index": index,
            "success": True,
            "tool_calls": [{"tool_name": tool, "arguments": {}, "success": True}],
        })
    task = {
        "task_id": "L2-passk-score",
        "level": 2,
        "golden_action": [{"tool": "A", "args": {}}],
        "tool_calls": [],
        "repetitions": 5,
        "repetition_results": [True] * 5,
        "repetition_records": records,
    }
    bench_task = {"task_id": "L2-passk-score", "golden_action": task["golden_action"]}
    summary = score_run.score_level("L2", {"results": [task]}, {"L2-passk-score": bench_task})
    _assert_close(summary["metrics"]["SelectAcc"]["score"], 0.2, "SelectAcc repeated average")
    _assert_close(summary["metrics"]["PassK_det"]["score"], 1.0, "PassK_det score")
    _assert(summary["metrics"]["PassK_det"]["in_score"] is False, "PassK_det in_score")
    _assert_close(summary["score"], 0.2, "PassK_det excluded from representative score")


def test_l6_passk_primary_is_coverage():
    _assert(
        level_spec.PASSK_PRIMARY_METRICS["L6"] == "Coverage",
        "L6 PassK_det primary must be Coverage",
    )


def test_redundant_call_rate_det_empty_trace_zero():
    ctx = DummyContext([{"action": "context_used"}], [])
    _assert_close(extra_metrics.redundant_call_rate_det(ctx), 0.0, "empty trace")


def test_redundant_call_rate_det_no_success_zero():
    ctx = DummyContext(
        [{"action": "context_used"}],
        [
            {"tool": "A", "args": {}, "success": False},
            {"tool": "A", "args": {}, "success": None},
        ],
    )
    _assert_close(extra_metrics.redundant_call_rate_det(ctx), 0.0, "no successful calls")


def test_redundant_call_rate_det_success_pass_through():
    ctx = DummyContext(
        [{"action": "context_used"}],
        [
            {"tool": "A", "args": {"q": "x"}, "success": True},
            {"tool": "A", "args": {"q": "x"}, "success": True},
        ],
    )
    expected = context.load_metrics_module().METRICS["RedundantCallRate"].evaluate(ctx).score
    _assert_close(
        extra_metrics.redundant_call_rate_det(ctx),
        expected,
        "successful calls pass through",
    )


def test_redundant_call_rate_det_gate_does_not_fire_on_success():
    """중복 호출 케이스는 vendored 값이 0.0 이라 게이트 오작동과 구분되지 않는다.

    고유 호출만 하면 vendored 가 1.0 을 주므로, 여기서 0.0 이 나오면
    게이트가 성공 호출에도 발동했다는 뜻이다.
    """
    ctx = DummyContext(
        [{"action": "context_used"}],
        [
            {"tool": "A", "args": {"q": "x"}, "success": True},
            {"tool": "B", "args": {"q": "y"}, "success": True},
        ],
    )
    _assert_close(
        extra_metrics.redundant_call_rate_det(ctx),
        1.0,
        "gate must not fire when calls succeeded",
    )


def test_l6_spec_redundant_call_rate_shape():
    specs = level_spec.LEVEL_SPECS["L6"]
    by_name = {spec.name: spec for spec in specs}
    _assert(specs[0].name == "RedundantCallRate_det", "L6 first metric")
    _assert(by_name["RedundantCallRate_det"].in_score is True, "det in_score")
    _assert(by_name["RedundantCallRate"].in_score is False, "raw record-only")
    _assert(
        sum(1 for spec in specs if spec.in_score) == 4,
        "L6 must have four representative metrics",
    )


def _l2_task(task_id, tool_name):
    return {
        "task_id": task_id,
        "level": 2,
        "golden_action": [{"tool": "A", "args": {}}],
        "tool_calls": [{"tool_name": tool_name, "arguments": {}, "success": True}],
    }


def _l6_no_call_task(task_id):
    return {
        "task_id": task_id,
        "level": 6,
        "golden_action": [
            {"tool": "A", "args": {}},
            {"action": "context_used"},
        ],
        "tool_calls": [],
    }


def _bench_map(tasks):
    return {
        task["task_id"]: {
            "task_id": task["task_id"],
            "golden_action": task["golden_action"],
        }
        for task in tasks
    }


def test_agent_score_task_count_weighting_differs_from_equal_mean():
    l2_tasks = [_l2_task("L2-weight-1", "A")]
    l6_tasks = [
        _l6_no_call_task("L6-weight-1"),
        _l6_no_call_task("L6-weight-2"),
        _l6_no_call_task("L6-weight-3"),
    ]
    summary = score_run.build_summary_from_loaded_for_test(
        {"L2": {"results": l2_tasks}, "L6": {"results": l6_tasks}},
        Path("/tmp/results/x/t/language/agent"),
        bench_task_maps={"L2": _bench_map(l2_tasks), "L6": _bench_map(l6_tasks)},
        bench_pin_value={"tasks_sha256": {}},
    )
    _assert_close(summary["by_level"]["L2"]["score"], 1.0, "L2 score")
    _assert_close(summary["by_level"]["L6"]["score"], 0.0, "L6 score")
    _assert_close(summary["agent_score"], 0.25, "weighted agent score")
    _assert_close(summary["agent_score_equal_level"], 0.5, "equal-level agent score")
    _assert(summary["agent_score"] != summary["agent_score_equal_level"], "scores should differ")
    _assert(summary["weighting"]["weights"] == {"L2": 1, "L6": 3}, "weights")


def test_agent_score_excludes_none_score_from_weighting():
    l2_tasks = [_l2_task("L2-weight-none", "A")]
    summary = score_run.build_summary_from_loaded_for_test(
        {"L2": {"results": l2_tasks}, "L7": {"results": []}},
        Path("/tmp/results/x/t/language/agent"),
        bench_task_maps={"L2": _bench_map(l2_tasks), "L7": {}},
        bench_pin_value={"tasks_sha256": {}},
    )
    _assert(summary["by_level"]["L7"]["score"] is None, "L7 should be unscorable")
    _assert_close(summary["agent_score"], 1.0, "weighted with None excluded")
    _assert(summary["weighting"]["weights"] == {"L2": 1}, "None score excluded")


def test_agent_score_no_scores_has_empty_weights():
    summary = score_run.build_summary_from_loaded_for_test(
        {"L7": {"results": []}},
        Path("/tmp/results/x/t/language/agent"),
        bench_task_maps={"L7": {}},
        bench_pin_value={"tasks_sha256": {}},
    )
    _assert(summary["agent_score"] is None, "no scores weighted score")
    _assert(summary["agent_score_equal_level"] is None, "no scores equal-level score")
    _assert(summary["weighting"]["weights"] == {}, "empty weights")


def test_data_health_no_tool_calls_warns():
    l6_tasks = [
        _l6_no_call_task("L6-health-empty-1"),
        _l6_no_call_task("L6-health-empty-2"),
    ]
    summary = score_run.build_summary_from_loaded_for_test(
        {"L6": {"results": l6_tasks}},
        Path("/tmp/results/x/t/language/agent"),
        bench_task_maps={"L6": _bench_map(l6_tasks)},
        bench_pin_value={"tasks_sha256": {}},
    )
    health = summary["data_health"]
    _assert(health["no_tool_calls_recorded"] is True, "empty tool calls should warn")
    _assert(health["total_tool_calls"] == 0, "empty total tool calls")
    _assert(health["tasks_with_tool_calls"] == 0, "empty tasks with tool calls")
    _assert("warning" in health, "warning key should be present")


def test_data_health_tool_calls_no_warning():
    l2_tasks = [_l2_task("L2-health-call", "A")]
    summary = score_run.build_summary_from_loaded_for_test(
        {"L2": {"results": l2_tasks}},
        Path("/tmp/results/x/t/language/agent"),
        bench_task_maps={"L2": _bench_map(l2_tasks)},
        bench_pin_value={"tasks_sha256": {}},
    )
    health = summary["data_health"]
    _assert(health["no_tool_calls_recorded"] is False, "tool calls should not warn")
    _assert(health["total_tool_calls"] == 1, "one total tool call")
    _assert("warning" not in health, "warning key should be absent")


def test_data_health_counts_repetition_record_tool_calls():
    task = {
        "task_id": "L2-health-repeat",
        "level": 2,
        "golden_action": [{"tool": "A", "args": {}}],
        "tool_calls": [],
        "repetitions": 2,
        "repetition_results": [True, True],
        "repetition_records": [
            {
                "rep_index": 0,
                "success": True,
                "tool_calls": [{"tool_name": "A", "arguments": {}, "success": True}],
            },
            {
                "rep_index": 1,
                "success": True,
                "tool_calls": [{"tool_name": "B", "arguments": {}, "success": True}],
            },
        ],
    }
    summary = score_run.build_summary_from_loaded_for_test(
        {"L2": {"results": [task]}},
        Path("/tmp/results/x/t/language/agent"),
        bench_task_maps={"L2": _bench_map([task])},
        bench_pin_value={"tasks_sha256": {}},
    )
    health = summary["data_health"]
    _assert(health["total_tool_calls"] == 2, "repetition tool calls counted")
    _assert(health["no_tool_calls_recorded"] is False, "repetition calls should not warn")


def test_data_health_empty_repetition_records_falls_back_to_parent():
    """빈 repetition_records 는 부모 tool_calls 로 폴백한다.

    _has_repetition_records 가 빈 리스트를 인정하지 않으므로 채점은 부모 tool_calls 로
    이뤄진다. data_health 가 다른 규칙을 쓰면 0 으로 잡혀 잘못된 경고가 뜬다.
    """
    task = {
        "task_id": "L2-health-empty-records",
        "level": 2,
        "golden_action": [{"tool": "A", "args": {}}],
        "tool_calls": [{"tool_name": "A", "arguments": {}, "success": True}],
        "repetition_records": [],
    }
    summary = score_run.build_summary_from_loaded_for_test(
        {"L2": {"results": [task]}},
        Path("/tmp/results/x/t/language/agent"),
        bench_task_maps={"L2": _bench_map([task])},
        bench_pin_value={"tasks_sha256": {}},
    )
    health = summary["data_health"]
    _assert(health["total_tool_calls"] == 1, "parent tool_calls counted on empty records")
    _assert(health["no_tool_calls_recorded"] is False, "must not warn when parent has calls")


def test_data_health_by_level_counts_loaded_levels():
    l2_tasks = [_l2_task("L2-health-level", "A")]
    l6_tasks = [
        _l6_no_call_task("L6-health-level-1"),
        _l6_no_call_task("L6-health-level-2"),
    ]
    summary = score_run.build_summary_from_loaded_for_test(
        {"L2": {"results": l2_tasks}, "L6": {"results": l6_tasks}},
        Path("/tmp/results/x/t/language/agent"),
        bench_task_maps={"L2": _bench_map(l2_tasks), "L6": _bench_map(l6_tasks)},
        bench_pin_value={"tasks_sha256": {}},
    )
    by_level = summary["data_health"]["by_level"]
    _assert(set(by_level) == {"L2", "L6"}, "data_health levels")
    _assert(
        by_level["L2"] == {"tasks": 1, "tasks_with_tool_calls": 1, "tool_calls": 1},
        "L2 data_health counts",
    )
    _assert(
        by_level["L6"] == {"tasks": 2, "tasks_with_tool_calls": 0, "tool_calls": 0},
        "L6 data_health counts",
    )


def test_data_health_empty_run_not_parser_warning():
    summary = score_run.build_summary_from_loaded_for_test(
        {"L7": {"results": []}},
        Path("/tmp/results/x/t/language/agent"),
        bench_task_maps={"L7": {}},
        bench_pin_value={"tasks_sha256": {}},
    )
    health = summary["data_health"]
    _assert(health["total_tasks"] == 0, "empty run total tasks")
    _assert(health["no_tool_calls_recorded"] is False, "empty run should not warn")


TESTS = [
    test_fsm_prefix_exact_match,
    test_fsm_prefix_with_extra_calls,
    test_fsm_prefix_wrong_order,
    test_fsm_prefix_empty_golden,
    test_fsm_prefix_empty_actual,
    test_mean_excludes_none,
    test_mean_all_none,
    test_in_score_false_excluded,
    test_judge_missing_without_call,
    test_missing_level_not_zero_filled,
    test_arg_f1_det_or_skip,
    test_l6_empty_tool_calls_not_full_score,
    test_l7_expected_action_synthesized_and_scored,
    test_l7_context_test_without_expected_action_skipped,
    test_golden_action_drift_records_error_not_zero,
    test_bench_task_none_keeps_existing_behavior,
    test_repetition_records_average_metric_entry,
    test_no_repetition_records_keeps_metric_entry_shape,
    test_passk_det_passes_if_one_repetition_primary_is_full,
    test_passk_det_not_in_representative_score,
    test_l6_passk_primary_is_coverage,
    test_redundant_call_rate_det_empty_trace_zero,
    test_redundant_call_rate_det_no_success_zero,
    test_redundant_call_rate_det_success_pass_through,
    test_redundant_call_rate_det_gate_does_not_fire_on_success,
    test_l6_spec_redundant_call_rate_shape,
    test_agent_score_task_count_weighting_differs_from_equal_mean,
    test_agent_score_excludes_none_score_from_weighting,
    test_agent_score_no_scores_has_empty_weights,
    test_data_health_no_tool_calls_warns,
    test_data_health_tool_calls_no_warning,
    test_data_health_counts_repetition_record_tool_calls,
    test_data_health_empty_repetition_records_falls_back_to_parent,
    test_data_health_by_level_counts_loaded_levels,
    test_data_health_empty_run_not_parser_warning,
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
