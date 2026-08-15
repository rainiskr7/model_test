from _harness import *

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
    summary = score_run.build_summary_from_loaded(
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
    test_l7_expected_action_synthesized_and_scored,
    test_l7_context_test_without_expected_action_skipped,
    test_golden_action_drift_records_error_not_zero,
    test_bench_task_none_keeps_existing_behavior,
    test_repetition_records_average_metric_entry,
    test_no_repetition_records_keeps_metric_entry_shape,
]
