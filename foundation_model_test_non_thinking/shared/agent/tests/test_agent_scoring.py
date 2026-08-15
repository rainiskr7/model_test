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


class MetricContext:
    def __init__(self, task_schema, final_response):
        self.task_schema = task_schema
        self.logs = {"final_response": final_response}


def _l6_schema(tool="ToolA", fields=None, result=None, final_seed_content="seeded answer"):
    fields = fields if fields is not None else ["item.title", "item.author"]
    result = result if result is not None else {"item": {"title": "책 제목", "author": "홍길동"}}
    return {
        "task_id": "L6-field",
        "task_level": 6,
        "golden_fields": [{"tool": tool, "fields": fields}],
        "conversation_tracking": {
            "turns": [
                {"turn_number": 1, "role": "user", "content": "찾아줘"},
                {
                    "turn_number": 2,
                    "role": "assistant",
                    "content": final_seed_content,
                    "action": {"tool": tool, "args": {}, "result": result},
                },
                {"turn_number": 3, "role": "user", "content": "아까 것 다시 알려줘"},
            ]
        },
    }


def _l6_metric(fields=None, result=None, final_response="", final_seed_content="seeded answer"):
    return extra_metrics.golden_field_recall_det(
        MetricContext(
            _l6_schema(fields=fields, result=result, final_seed_content=final_seed_content),
            final_response,
        )
    )


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
        "final_response": "책 제목은 책 제목이고 저자는 홍길동입니다.",
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
        "golden_fields": [{"tool": "ToolA", "fields": ["item.title", "item.author"]}],
        "conversation_tracking": _l6_schema()["conversation_tracking"],
    }
    ctx = context.build_eval_context(task, bench_task)
    _assert_close(extra_metrics.call_eff_det(ctx), 0.0, "empty calls call_eff_det")

    summary = score_run.score_level("L6", {"results": [task]}, {"L6-x": bench_task})
    _assert_close(
        summary["metrics"]["GoldenFieldRecall_det"]["score"],
        1.0,
        "L6 GoldenFieldRecall_det",
    )
    _assert_close(summary["metrics"]["CallEff_det"]["score"], 0.0, "L6 CallEff_det")
    _assert_close(summary["metrics"]["ToolAcc"]["score"], 0.0, "L6 ToolAcc")
    _assert_close(summary["metrics"]["Coverage"]["score"], 0.0, "L6 Coverage")
    _assert(summary["metrics"]["CallEff_det"]["in_score"] is False, "CallEff_det record-only")
    _assert(summary["metrics"]["ToolAcc"]["in_score"] is False, "ToolAcc record-only")
    _assert(summary["metrics"]["Coverage"]["in_score"] is False, "Coverage record-only")
    _assert_close(summary["score"], 1.0, "L6 representative score")


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
    _assert_close(
        summary["score"],
        0.13333333333333333,
        "PassK_det excluded from representative score",
    )


def test_golden_field_recall_happy_path():
    _assert_close(
        _l6_metric(final_response="책 제목 / 홍길동 정보를 다시 알려드립니다."),
        1.0,
        "two golden fields matched",
    )


def test_golden_field_recall_partial():
    _assert_close(
        _l6_metric(final_response="책 제목만 다시 알려드립니다."),
        0.5,
        "one of two golden fields matched",
    )


def test_golden_field_recall_seeded_echo_zero():
    seed = "책 제목은 책 제목이고 저자는 홍길동입니다."
    _assert_close(
        _l6_metric(final_response=seed, final_seed_content=seed),
        0.0,
        "seeded echo guard",
    )


def test_golden_field_recall_html_tags_expected_and_response():
    _assert_close(
        _l6_metric(
            fields=["item.title"],
            result={"item": {"title": "<b>겨울</b> 제주도"}},
            final_response="겨울 제주도 추천입니다.",
        ),
        1.0,
        "expected HTML tags stripped",
    )
    _assert_close(
        _l6_metric(
            fields=["item.title"],
            result={"item": {"title": "겨울 제주도"}},
            final_response="<b>겨울</b> 제주도 추천입니다.",
        ),
        1.0,
        "response HTML tags stripped",
    )


def test_golden_field_recall_category_arrows_preserved():
    _assert_close(
        _l6_metric(
            fields=["item.category"],
            result={"item": {"category": "음식점 > 중식 > 중국요리"}},
            final_response="분류는 음식점 > 중식 > 중국요리입니다.",
        ),
        1.0,
        "category arrows must not be stripped",
    )


def test_golden_field_recall_numeric_comma_match():
    _assert_close(
        _l6_metric(
            fields=["item.priceSales"],
            result={"item": {"priceSales": 34200}},
            final_response="가격은 34,200원입니다.",
        ),
        1.0,
        "numeric comma normalization",
    )


def test_golden_field_recall_description_contents_filtered():
    score = _l6_metric(
        fields=["item.description", "item.contents"],
        result={"item": {"description": "설명", "contents": "본문"}},
        final_response="설명 본문",
    )
    _assert(score is None, "description/contents only should be not applicable")


def test_golden_field_recall_unresolved_excluded_from_denominator():
    _assert_close(
        _l6_metric(
            fields=["item.missing", "item.title"],
            result={"item": {"title": "책 제목"}},
            final_response="책 제목입니다.",
        ),
        1.0,
        "unresolved fields excluded",
    )


def test_l6_resolve_field_with_fallback_exact_wins():
    result = {
        "data": [{"date": "exact"}],
        "chart_data": [{"date": "fallback"}],
    }
    resolved, value, used_fallback = extra_metrics.l6_resolve_field_with_fallback(
        result, "data[0].date"
    )
    _assert(resolved is True, "exact path should resolve")
    _assert(value == "exact", "exact value should win")
    _assert(used_fallback is False, "exact resolution must not mark fallback")


def test_l6_resolve_field_with_fallback_unique_list_leaf():
    result = {"chart_data": [{"date": "20250926"}]}
    resolved, value, used_fallback = extra_metrics.l6_resolve_field_with_fallback(
        result, "data[0].date"
    )
    _assert(resolved is True, "unique fallback should resolve")
    _assert(value == "20250926", "unique fallback value")
    _assert(used_fallback is True, "unique fallback should be marked")


def test_l6_resolve_field_with_fallback_ambiguous_unresolved():
    result = {
        "chart_data": [{"date": "20250926"}],
        "other_data": [{"date": "20250927"}],
    }
    resolved, value, used_fallback = extra_metrics.l6_resolve_field_with_fallback(
        result, "data[0].date"
    )
    _assert(resolved is False, "ambiguous fallback should stay unresolved")
    _assert(value is None, "ambiguous fallback must not pick a value")
    _assert(used_fallback is False, "ambiguous fallback must not be marked")


def test_l6_resolve_field_with_fallback_scalar_suffix():
    resolved, value, used_fallback = extra_metrics.l6_resolve_field_with_fallback(
        {"market_count": 120}, "count"
    )
    _assert(resolved is True, "scalar suffix fallback should resolve")
    _assert(value == 120, "scalar suffix fallback value")
    _assert(used_fallback is True, "scalar suffix fallback should be marked")

    resolved, value, used_fallback = extra_metrics.l6_resolve_field_with_fallback(
        {"count": 5}, "count"
    )
    _assert(resolved is True, "exact scalar key should resolve")
    _assert(value == 5, "exact scalar key value")
    _assert(used_fallback is False, "exact scalar key must not use fallback")


def test_l6_golden_field_diagnostics_counts_fallback_fields():
    schema = _l6_schema(
        fields=["data[0].date", "data[0].missing"],
        result={"chart_data": [{"date": "20250926"}]},
    )
    diagnostics = extra_metrics.l6_golden_field_diagnostics(
        MetricContext(schema, "20250926")
    )
    _assert(diagnostics["fallback_fields"] == 1, "fallback field count")
    _assert(diagnostics["unresolved_fields"] == 1, "only unresolved field remains unresolved")
    _assert(diagnostics["scorable_values"] == ["20250926"], "fallback value is scorable")


def test_golden_field_recall_evaluation_turn_boundary():
    schema = {
        "golden_fields": [{"tool": "ToolA", "fields": ["item.title"]}],
        "conversation_tracking": {
            "evaluation_context": {"context_tests": [{"turn": 1}]},
            "turns": [
                {"turn_number": 1, "role": "user", "content": "평가 질문"},
                {
                    "turn_number": 2,
                    "role": "assistant",
                    "content": "평가 뒤 답변",
                    "action": {
                        "tool": "ToolA",
                        "args": {},
                        "result": {"item": {"title": "나중 제목"}},
                    },
                },
            ],
        },
    }
    score = extra_metrics.golden_field_recall_det(MetricContext(schema, "나중 제목"))
    _assert(score is None, "post-evaluation tool result must not be seeded")


def test_no_refetch_det_empty_action_trace():
    _assert_close(extra_metrics.no_refetch_det(DummyContext([], [])), 1.0, "empty action trace")


def test_no_refetch_det_any_call_including_failed():
    _assert_close(
        extra_metrics.no_refetch_det(DummyContext([], [{"tool": "A", "success": True}])),
        0.0,
        "one call",
    )
    _assert_close(
        extra_metrics.no_refetch_det(
            DummyContext([], [{"tool": "A", "success": False, "error": "failed"}])
        ),
        0.0,
        "failed call still refetch",
    )


def test_l6_refetch_with_correct_answer_not_full_score():
    task = {
        "task_id": "L6-refetch-correct",
        "level": 6,
        "final_response": "책 제목과 홍길동 정보를 다시 알려드립니다.",
        "golden_action": [{"action": "context_used"}],
        "tool_calls": [{"tool_name": "ToolA", "arguments": {}, "success": True}],
    }
    bench_task = {
        "task_id": "L6-refetch-correct",
        "golden_action": task["golden_action"],
        "golden_fields": [{"tool": "ToolA", "fields": ["item.title", "item.author"]}],
        "conversation_tracking": _l6_schema()["conversation_tracking"],
    }
    summary = score_run.score_level("L6", {"results": [task]}, {"L6-refetch-correct": bench_task})
    _assert_close(
        summary["metrics"]["GoldenFieldRecall_det"]["score"],
        1.0,
        "correct seeded field answer",
    )
    _assert_close(summary["metrics"]["NoRefetch_det"]["score"], 0.0, "refetch penalty")
    _assert(summary["score"] < 1.0, "L6 level score must penalize refetch")


def test_l6_no_refetch_with_correct_answer_full_score():
    task = {
        "task_id": "L6-no-refetch-correct",
        "level": 6,
        "final_response": "책 제목과 홍길동 정보를 다시 알려드립니다.",
        "golden_action": [{"action": "context_used"}],
        "tool_calls": [],
    }
    bench_task = {
        "task_id": "L6-no-refetch-correct",
        "golden_action": task["golden_action"],
        "golden_fields": [{"tool": "ToolA", "fields": ["item.title", "item.author"]}],
        "conversation_tracking": _l6_schema()["conversation_tracking"],
    }
    summary = score_run.score_level("L6", {"results": [task]}, {"L6-no-refetch-correct": bench_task})
    _assert_close(
        summary["metrics"]["GoldenFieldRecall_det"]["score"],
        1.0,
        "correct seeded field answer",
    )
    _assert_close(summary["metrics"]["NoRefetch_det"]["score"], 1.0, "no refetch")
    _assert_close(summary["score"], 1.0, "L6 no-refetch correct answer full score")


def test_l4_meaningful_result_predicate():
    _assert(extra_metrics.l4_has_meaningful_result(["x"]) is True, "non-empty list")
    _assert(extra_metrics.l4_has_meaningful_result([]) is False, "empty list")
    _assert(extra_metrics.l4_has_meaningful_result({}) is False, "empty dict")
    _assert(
        extra_metrics.l4_has_meaningful_result({"items": []}) is False,
        "only empty list",
    )
    _assert(
        extra_metrics.l4_has_meaningful_result({"items": [], "documents": [{"id": 1}]}) is True,
        "one non-empty list",
    )
    _assert(
        extra_metrics.l4_has_meaningful_result({"price": 58200}) is True,
        "dict with no list",
    )
    _assert(extra_metrics.l4_has_meaningful_result(None) is False, "None")
    _assert(extra_metrics.l4_has_meaningful_result("") is False, "empty string")


def test_l4_stock_trades_empty_payload_not_meaningful():
    result = {
        "t8454OutBlock": {"rsp_cd": "00000"},
        "t8454OutBlock1": [],
        "rsp_cd": "00000",
        "rsp_msg": "해당자료가 없습니다.",
    }
    _assert(extra_metrics.l4_has_meaningful_result(result) is False, "empty trade payload")


def test_l4_stock_quote_shape_meaningful():
    result = {"t1102OutBlock": {"price": 58200}, "rsp_cd": "00000"}
    _assert(extra_metrics.l4_has_meaningful_result(result) is True, "stock quote payload")


def test_l4_coverage_det_recovers_non_search_shape():
    ctx = DummyContext(
        [{"tool": "StockPrice_ls"}, {"tool": "Geocoding_tmap"}],
        [
            {
                "tool": "StockPrice_ls",
                "success": True,
                "error": None,
                "result": {"t1102OutBlock": {"price": 58200}, "rsp_cd": "00000"},
            }
        ],
    )
    _assert_close(extra_metrics.coverage_det(ctx), 0.5, "Coverage_det non-search recovery")
    vendored = level_spec.vendored_metric("Coverage")(ctx)
    _assert_close(vendored, 0.0, "vendored Coverage misses non-search shape")


def test_l4_source_epr_det_counts_meaningful_calls():
    ctx = DummyContext(
        [{"tool": "StockPrice_ls"}, {"tool": "Geocoding_tmap"}],
        [
            {
                "tool": "StockPrice_ls",
                "success": True,
                "error": None,
                "result": {"t1102OutBlock": {"price": 58200}, "rsp_cd": "00000"},
            },
            {
                "tool": "StockPrice_ls",
                "success": True,
                "error": None,
                "result": {"items": []},
            },
        ],
    )
    _assert_close(extra_metrics.source_epr_det(ctx), 0.25, "SourceEPR_det mixed calls")


def test_l4_spec_shape_and_passk_primary():
    specs = level_spec.LEVEL_SPECS["L4"]
    by_name = {spec.name: spec for spec in specs}
    in_score = [spec for spec in specs if spec.in_score]
    _assert(
        [spec.name for spec in in_score] == ["Coverage_det", "SourceEPR_det"],
        "L4 representative metrics",
    )
    _assert(by_name["Coverage"].in_score is False, "vendored Coverage record-only")
    _assert(by_name["SourceEPR"].in_score is False, "vendored SourceEPR record-only")
    primary = level_spec.PASSK_PRIMARY_METRICS["L4"]
    _assert(primary == "Coverage_det", "L4 PassK_det primary")
    _assert(primary in by_name, "L4 PassK_det primary must resolve")


def test_l4_change_leaves_l6_and_l3_shapes_unchanged():
    _assert(
        len([spec for spec in level_spec.LEVEL_SPECS["L6"] if spec.in_score]) == 2,
        "L6 representative metric count",
    )
    _assert(
        [spec.name for spec in level_spec.LEVEL_SPECS["L6"] if spec.in_score]
        == ["GoldenFieldRecall_det", "NoRefetch_det"],
        "L6 representative metric name",
    )
    _assert(
        len(level_spec.LEVEL_SPECS["L3"]) == 5,
        "L3 total metric count",
    )
    _assert(
        len([spec for spec in level_spec.LEVEL_SPECS["L3"] if spec.in_score]) == 4,
        "L3 representative metric count",
    )


def test_l6_spec_shape_and_passk_primary():
    _assert(
        level_spec.PASSK_PRIMARY_METRICS["L6"] == "GoldenFieldRecall_det",
        "L6 PassK_det primary must be GoldenFieldRecall_det",
    )
    specs = level_spec.LEVEL_SPECS["L6"]
    in_score = [spec for spec in specs if spec.in_score]
    _assert(specs[0].name == "GoldenFieldRecall_det", "L6 first metric")
    _assert(
        [spec.name for spec in in_score] == ["GoldenFieldRecall_det", "NoRefetch_det"],
        "L6 representative metrics",
    )
    _assert(
        [spec.name for spec in specs]
        == [
            "GoldenFieldRecall_det",
            "NoRefetch_det",
            "RedundantCallRate",
            "ToolAcc",
            "Coverage",
            "CallEff_det",
        ],
        "L6 metric order",
    )
    _assert(level_spec.LEVEL_SPECS["L6"][2].in_score is False, "RedundantCallRate record-only")
    _assert(level_spec.LEVEL_SPECS["L6"][3].in_score is False, "ToolAcc record-only")
    _assert(level_spec.LEVEL_SPECS["L6"][4].in_score is False, "Coverage record-only")
    _assert(level_spec.LEVEL_SPECS["L6"][5].in_score is False, "CallEff_det record-only")


def test_l3_spec_shape():
    specs = level_spec.LEVEL_SPECS["L3"]
    by_name = {spec.name: spec for spec in specs}
    _assert(specs[0].name == "FSM_prefix", "L3 first metric")
    _assert(by_name["FSM_prefix"].in_score is True, "FSM_prefix in_score")
    _assert(by_name["FSM_strict"].in_score is False, "FSM_strict record-only")
    _assert(
        {spec.name for spec in specs if spec.in_score}
        == {"FSM_prefix", "PSM", "ΔSteps_norm", "ArgF1_det"},
        "L3 representative metrics",
    )


def test_l3_passk_primary_resolves_to_spec():
    primary = level_spec.PASSK_PRIMARY_METRICS["L3"]
    _assert(primary == "FSM_prefix", "L3 PassK_det primary")
    spec = next((spec for spec in level_spec.LEVEL_SPECS["L3"] if spec.name == primary), None)
    _assert(spec is not None, "L3 PassK_det primary must resolve")


def test_l3_representative_score_excludes_fsm_strict():
    task = {
        "task_id": "L3-prefix-extra",
        "level": 3,
        "golden_action": [
            {"tool": "Search", "args": {"q": "alpha"}},
            {"tool": "Read", "args": {"id": "doc-1"}},
        ],
        "minimum_steps": 2,
        "arg_schema": {},
        "tool_calls": [
            {
                "tool_name": "Search",
                "arguments": {"q": "alpha"},
                "success": True,
            },
            {
                "tool_name": "Read",
                "arguments": {"id": "doc-1"},
                "success": True,
            },
            {
                "tool_name": "Search",
                "arguments": {"q": "retry"},
                "success": False,
                "error": "Pseudo-API(read): cache miss",
            },
        ],
    }
    bench_task = {
        "task_id": "L3-prefix-extra",
        "golden_action": task["golden_action"],
        "minimum_steps": 2,
    }
    summary = score_run.score_level("L3", {"results": [task]}, {"L3-prefix-extra": bench_task})
    metrics = summary["metrics"]
    _assert_close(metrics["FSM_prefix"]["score"], 1.0, "L3 FSM_prefix")
    _assert_close(metrics["FSM_strict"]["score"], 0.0, "L3 FSM_strict")
    _assert(metrics["FSM_strict"]["in_score"] is False, "FSM_strict record-only")
    expected = (
        metrics["FSM_prefix"]["score"]
        + metrics["PSM"]["score"]
        + metrics["ΔSteps_norm"]["score"]
        + metrics["ArgF1_det"]["score"]
    ) / 4
    _assert_close(summary["score"], expected, "L3 score excludes FSM_strict")
    _assert(summary["score"] > 0.0, "L3 score unaffected by zero FSM_strict")


def test_l2_spec_shape():
    in_score = [spec for spec in level_spec.LEVEL_SPECS["L2"] if spec.in_score]
    _assert(
        [spec.name for spec in in_score] == ["SelectAcc", "CallEM", "ArgF1_det"],
        "L2 representative metrics",
    )


def test_l2_passk_primary_resolves_to_spec():
    primary = level_spec.PASSK_PRIMARY_METRICS["L2"]
    _assert(primary == "SelectAcc", "L2 PassK_det primary")
    spec = next((spec for spec in level_spec.LEVEL_SPECS["L2"] if spec.name == primary), None)
    _assert(spec is not None, "L2 PassK_det primary must resolve")


def test_l2_correct_tool_wrong_args_not_full_score():
    task = {
        "task_id": "L2-wrong-args",
        "level": 2,
        "golden_action": [{"tool": "A", "args": {"q": "gold", "count": 30}}],
        "tool_calls": [
            {
                "tool_name": "A",
                "arguments": {"q": "actual"},
                "success": True,
            }
        ],
    }
    bench_task = {"task_id": "L2-wrong-args", "golden_action": task["golden_action"]}
    summary = score_run.score_level("L2", {"results": [task]}, {"L2-wrong-args": bench_task})
    metrics = summary["metrics"]
    _assert_close(metrics["SelectAcc"]["score"], 1.0, "L2 SelectAcc ignores args")
    _assert(metrics["CallEM"]["score"] < 1.0, "L2 CallEM catches wrong args")
    _assert(metrics["ArgF1_det"]["score"] < 1.0, "L2 ArgF1_det catches wrong args")
    _assert(summary["score"] < 1.0, "L2 representative score must not be full")


def test_other_level_shapes_unchanged():
    _assert(
        len([spec for spec in level_spec.LEVEL_SPECS["L1"] if spec.in_score]) == 3,
        "L1 representative metric count",
    )
    _assert(
        len([spec for spec in level_spec.LEVEL_SPECS["L2"] if spec.in_score]) == 3,
        "L2 representative metric count",
    )
    _assert(
        len([spec for spec in level_spec.LEVEL_SPECS["L3"] if spec.in_score]) == 4,
        "L3 representative metric count",
    )
    _assert(
        len([spec for spec in level_spec.LEVEL_SPECS["L4"] if spec.in_score]) == 2,
        "L4 representative metric count",
    )
    _assert(
        len([spec for spec in level_spec.LEVEL_SPECS["L7"] if spec.in_score]) == 3,
        "L7 representative metric count",
    )
    _assert(level_spec.PASSK_PRIMARY_METRICS["L1"] == "CallEM", "L1 PassK_det primary")


def _l2_task(task_id, tool_name):
    return {
        "task_id": task_id,
        "level": 2,
        "golden_action": [{"tool": "A", "args": {"q": "x"}}],
        "tool_calls": [{"tool_name": tool_name, "arguments": {"q": "x"}, "success": True}],
    }


def _l6_no_call_task(task_id):
    return {
        "task_id": task_id,
        "level": 6,
        "final_response": "",
        "golden_action": [
            {"tool": "A", "args": {}},
            {"action": "context_used"},
        ],
        "golden_fields": [{"tool": "ToolA", "fields": ["item.title"]}],
        "conversation_tracking": _l6_schema(
            fields=["item.title"],
            result={"item": {"title": "seeded title"}},
        )["conversation_tracking"],
        "tool_calls": [],
    }


def _bench_map(tasks):
    mapped = {}
    for task in tasks:
        bench_task = {
            "task_id": task["task_id"],
            "golden_action": task["golden_action"],
        }
        for key in ("golden_fields", "conversation_tracking", "minimum_calls"):
            if key in task:
                bench_task[key] = task[key]
        mapped[task["task_id"]] = bench_task
    return mapped


def test_agent_score_scored_task_count_weighting_differs_from_equal_mean():
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
    _assert_close(summary["by_level"]["L6"]["score"], 0.5, "L6 score")
    _assert_close(summary["agent_score"], 0.625, "weighted agent score")
    _assert_close(summary["agent_score_equal_level"], 0.75, "equal-level agent score")
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
        by_level["L2"] == {
            "tasks": 1,
            "tasks_with_tool_calls": 1,
            "tool_calls": 1,
            "zero_step_tasks": 1,
            "empty_response_tasks": 1,
        },
        "L2 data_health counts",
    )
    _assert(
        by_level["L6"] == {
            "tasks": 2,
            "tasks_with_tool_calls": 0,
            "tool_calls": 0,
            "zero_step_tasks": 2,
            "empty_response_tasks": 2,
            "seeded_echo_tasks": 0,
            "unresolved_field_tasks": 0,
            "scored_tasks": 2,
            "fallback_resolved_fields": 0,
        },
        "L6 data_health counts",
    )


def test_data_health_l6_fallback_key_and_non_l6_l3_absent():
    l6_task = _l6_no_call_task("L6-health-fallback")
    l6_task["golden_fields"] = [{"tool": "ToolA", "fields": ["data[0].date"]}]
    l6_task["conversation_tracking"] = _l6_schema(
        fields=["data[0].date"],
        result={"chart_data": [{"date": "20250926"}]},
    )["conversation_tracking"]
    l2_tasks = [_l2_task("L2-health-no-fallback-key", "A")]
    summary = score_run.build_summary_from_loaded_for_test(
        {"L6": {"results": [l6_task]}, "L2": {"results": l2_tasks}},
        Path("/tmp/results/x/t/language/agent"),
        bench_task_maps={"L6": _bench_map([l6_task]), "L2": _bench_map(l2_tasks)},
        bench_pin_value={"tasks_sha256": {}},
    )
    by_level = summary["data_health"]["by_level"]
    _assert(
        by_level["L6"]["fallback_resolved_fields"] == 1,
        "L6 fallback_resolved_fields",
    )
    _assert(
        "fallback_resolved_fields" not in by_level["L2"],
        "non-L6/L3 must not include fallback_resolved_fields",
    )


def test_data_health_l3_prefix_only_tasks():
    prefix_task = {
        "task_id": "L3-health-prefix",
        "level": 3,
        "golden_action": [
            {"tool": "Search", "args": {"q": "alpha"}},
            {"tool": "Read", "args": {"id": "doc-1"}},
        ],
        "minimum_steps": 2,
        "arg_schema": {},
        "tool_calls": [
            {"tool_name": "Search", "arguments": {"q": "alpha"}, "success": True},
            {"tool_name": "Read", "arguments": {"id": "doc-1"}, "success": True},
            {"tool_name": "Search", "arguments": {"q": "extra"}, "success": True},
        ],
    }
    exact_task = {
        "task_id": "L3-health-exact",
        "level": 3,
        "golden_action": [
            {"tool": "Search", "args": {"q": "beta"}},
            {"tool": "Read", "args": {"id": "doc-2"}},
        ],
        "minimum_steps": 2,
        "arg_schema": {},
        "tool_calls": [
            {"tool_name": "Search", "arguments": {"q": "beta"}, "success": True},
            {"tool_name": "Read", "arguments": {"id": "doc-2"}, "success": True},
        ],
    }
    summary = score_run.build_summary_from_loaded_for_test(
        {"L3": {"results": [prefix_task, exact_task]}},
        Path("/tmp/results/x/t/language/agent"),
        bench_task_maps={"L3": _bench_map([prefix_task, exact_task])},
        bench_pin_value={"tasks_sha256": {}},
    )
    by_level = summary["data_health"]["by_level"]
    _assert(by_level["L3"]["prefix_only_tasks"] == 1, "one prefix-only L3 task")
    _assert(
        score_run._l3_data_health([exact_task], _bench_map([exact_task]))["prefix_only_tasks"] == 0,
        "exact L3 task is not prefix-only",
    )
    _assert(
        "fallback_resolved_fields" not in by_level["L3"],
        "L3 must not include L6 fallback key",
    )


def test_l6_data_health_load_guard():
    task = _l6_no_call_task("L6-health-load-guard")
    original = score_run.load_bench_tasks

    def _raise_load(_level):
        raise RuntimeError("boom")

    score_run.load_bench_tasks = _raise_load
    try:
        health = score_run._l6_data_health([task], None)
    finally:
        score_run.load_bench_tasks = original

    _assert(isinstance(health, dict), "load failure should return health dict")


def test_l6_data_health_field_diagnostics_and_non_l6_shape():
    echo_text = "책 제목과 홍길동"
    echo_task = {
        "task_id": "L6-health-echo",
        "level": 6,
        "final_response": echo_text,
        "golden_action": [{"action": "context_used"}],
        "golden_fields": [{"tool": "ToolA", "fields": ["item.title", "item.author"]}],
        "conversation_tracking": _l6_schema(final_seed_content=echo_text)["conversation_tracking"],
        "tool_calls": [],
    }
    unresolved_task = {
        "task_id": "L6-health-unresolved",
        "level": 6,
        "final_response": "책 제목",
        "golden_action": [{"action": "context_used"}],
        "golden_fields": [{"tool": "ToolA", "fields": ["item.missing", "item.title"]}],
        "conversation_tracking": _l6_schema(
            fields=["item.missing", "item.title"],
            result={"item": {"title": "책 제목"}},
        )["conversation_tracking"],
        "tool_calls": [],
    }
    filtered_task = {
        "task_id": "L6-health-filtered",
        "level": 6,
        "final_response": "설명",
        "golden_action": [{"action": "context_used"}],
        "golden_fields": [{"tool": "ToolA", "fields": ["item.description"]}],
        "conversation_tracking": _l6_schema(
            fields=["item.description"],
            result={"item": {"description": "설명"}},
        )["conversation_tracking"],
        "tool_calls": [],
    }
    l2_tasks = [_l2_task("L2-health-shape", "A")]
    l6_tasks = [echo_task, unresolved_task, filtered_task]
    summary = score_run.build_summary_from_loaded_for_test(
        {"L6": {"results": l6_tasks}, "L2": {"results": l2_tasks}},
        Path("/tmp/results/x/t/language/agent"),
        bench_task_maps={"L6": _bench_map(l6_tasks), "L2": _bench_map(l2_tasks)},
        bench_pin_value={"tasks_sha256": {}},
    )
    by_level = summary["data_health"]["by_level"]
    _assert(by_level["L6"]["seeded_echo_tasks"] == 1, "L6 seeded echo count")
    _assert(by_level["L6"]["unresolved_field_tasks"] == 1, "L6 unresolved count")
    _assert(by_level["L6"]["scored_tasks"] == 2, "L6 scored count")
    _assert(by_level["L6"]["fallback_resolved_fields"] == 0, "L6 fallback count")
    for key in (
        "seeded_echo_tasks",
        "unresolved_field_tasks",
        "scored_tasks",
        "fallback_resolved_fields",
        "prefix_only_tasks",
    ):
        _assert(key not in by_level["L2"], f"non-L6 must not include {key}")


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


def test_data_health_counts_zero_step_tasks():
    tasks = [
        {
            "task_id": "L1-zero-step",
            "level": 1,
            "golden_action": [],
            "tool_calls": [],
            "steps_taken": 0,
            "final_response": "done",
        },
        {
            "task_id": "L1-positive-step",
            "level": 1,
            "golden_action": [],
            "tool_calls": [],
            "steps_taken": 1,
            "final_response": "done",
        },
    ]
    summary = score_run.build_summary_from_loaded_for_test(
        {"L1": {"results": tasks}},
        Path("/tmp/results/x/t/language/agent"),
        bench_task_maps={"L1": _bench_map(tasks)},
        bench_pin_value={"tasks_sha256": {}},
    )
    health = summary["data_health"]
    _assert(health["by_level"]["L1"]["zero_step_tasks"] == 1, "one zero-step task")
    _assert(health["zero_step_tasks"] == 1, "zero-step rollup")


def test_data_health_missing_steps_taken_counts_zero():
    task = {
        "task_id": "L1-missing-step",
        "level": 1,
        "golden_action": [],
        "tool_calls": [],
        "final_response": "done",
    }
    summary = score_run.build_summary_from_loaded_for_test(
        {"L1": {"results": [task]}},
        Path("/tmp/results/x/t/language/agent"),
        bench_task_maps={"L1": _bench_map([task])},
        bench_pin_value={"tasks_sha256": {}},
    )
    _assert(
        summary["data_health"]["by_level"]["L1"]["zero_step_tasks"] == 1,
        "missing steps_taken counts as zero",
    )


def test_data_health_counts_empty_response_tasks():
    tasks = [
        {
            "task_id": "L1-response-none",
            "level": 1,
            "golden_action": [],
            "tool_calls": [],
            "steps_taken": 1,
            "final_response": None,
        },
        {
            "task_id": "L1-response-missing",
            "level": 1,
            "golden_action": [],
            "tool_calls": [],
            "steps_taken": 1,
        },
        {
            "task_id": "L1-response-empty",
            "level": 1,
            "golden_action": [],
            "tool_calls": [],
            "steps_taken": 1,
            "final_response": "",
        },
        {
            "task_id": "L1-response-space",
            "level": 1,
            "golden_action": [],
            "tool_calls": [],
            "steps_taken": 1,
            "final_response": "   ",
        },
        {
            "task_id": "L1-response-text",
            "level": 1,
            "golden_action": [],
            "tool_calls": [],
            "steps_taken": 1,
            "final_response": "done",
        },
    ]
    summary = score_run.build_summary_from_loaded_for_test(
        {"L1": {"results": tasks}},
        Path("/tmp/results/x/t/language/agent"),
        bench_task_maps={"L1": _bench_map(tasks)},
        bench_pin_value={"tasks_sha256": {}},
    )
    health = summary["data_health"]
    _assert(health["by_level"]["L1"]["empty_response_tasks"] == 4, "four empty responses")
    _assert(health["empty_response_tasks"] == 4, "empty-response rollup")


def test_data_health_new_keys_on_non_special_level_and_score_unchanged():
    tasks = [_l2_task("L2-additive-score", "A")]
    tasks[0]["steps_taken"] = 1
    tasks[0]["final_response"] = "selected A"
    summary = score_run.build_summary_from_loaded_for_test(
        {"L2": {"results": tasks}},
        Path("/tmp/results/x/t/language/agent"),
        bench_task_maps={"L2": _bench_map(tasks)},
        bench_pin_value={"tasks_sha256": {}},
    )
    health = summary["data_health"]
    _assert("zero_step_tasks" in health["by_level"]["L2"], "L2 zero_step_tasks key")
    _assert("empty_response_tasks" in health["by_level"]["L2"], "L2 empty_response_tasks key")
    _assert(health["by_level"]["L2"]["zero_step_tasks"] == 0, "L2 zero-step count")
    _assert(health["by_level"]["L2"]["empty_response_tasks"] == 0, "L2 empty-response count")
    _assert_close(summary["agent_score"], 1.0, "agent score unchanged")
    _assert(summary["weighting"] == {"scheme": "scored_task_count", "weights": {"L2": 1}}, "weighting")
    _assert_close(summary["by_level"]["L2"]["score"], 1.0, "L2 score unchanged")


def test_data_health_rollup_sums_levels():
    l1_tasks = [
        {
            "task_id": "L1-rollup-zero",
            "level": 1,
            "golden_action": [],
            "tool_calls": [],
            "steps_taken": 0,
            "final_response": "",
        }
    ]
    l2_tasks = [
        {
            "task_id": "L2-rollup-ok",
            "level": 2,
            "golden_action": [{"tool": "A", "args": {}}],
            "tool_calls": [{"tool_name": "A", "arguments": {}, "success": True}],
            "steps_taken": 1,
            "final_response": "done",
        },
        {
            "task_id": "L2-rollup-empty",
            "level": 2,
            "golden_action": [{"tool": "A", "args": {}}],
            "tool_calls": [],
            "steps_taken": 1,
            "final_response": None,
        },
    ]
    summary = score_run.build_summary_from_loaded_for_test(
        {"L1": {"results": l1_tasks}, "L2": {"results": l2_tasks}},
        Path("/tmp/results/x/t/language/agent"),
        bench_task_maps={"L1": _bench_map(l1_tasks), "L2": _bench_map(l2_tasks)},
        bench_pin_value={"tasks_sha256": {}},
    )
    by_level = summary["data_health"]["by_level"]
    _assert(
        summary["data_health"]["zero_step_tasks"]
        == by_level["L1"]["zero_step_tasks"] + by_level["L2"]["zero_step_tasks"],
        "zero-step rollup sums levels",
    )
    _assert(
        summary["data_health"]["empty_response_tasks"]
        == by_level["L1"]["empty_response_tasks"] + by_level["L2"]["empty_response_tasks"],
        "empty-response rollup sums levels",
    )


def test_data_health_repetition_records_zero_step_and_empty_response():
    mixed_steps = {
        "task_id": "L1-repeat-mixed-steps",
        "level": 1,
        "golden_action": [],
        "tool_calls": [],
        "steps_taken": 0,
        "final_response": "",
        "repetition_records": [
            {"steps_taken": 0, "final_response": ""},
            {"steps_taken": 1, "final_response": ""},
        ],
    }
    all_zero_steps = {
        "task_id": "L1-repeat-all-zero",
        "level": 1,
        "golden_action": [],
        "tool_calls": [],
        "steps_taken": 0,
        "final_response": "parent ignored",
        "repetition_records": [
            {"steps_taken": 0, "final_response": ""},
            {"final_response": "   "},
        ],
    }
    one_nonempty_response = {
        "task_id": "L1-repeat-nonempty-response",
        "level": 1,
        "golden_action": [],
        "tool_calls": [],
        "steps_taken": 0,
        "final_response": "",
        "repetition_records": [
            {"steps_taken": 0, "final_response": ""},
            {"steps_taken": 0, "final_response": "done"},
        ],
    }
    tasks = [mixed_steps, all_zero_steps, one_nonempty_response]
    summary = score_run.build_summary_from_loaded_for_test(
        {"L1": {"results": tasks}},
        Path("/tmp/results/x/t/language/agent"),
        bench_task_maps={"L1": _bench_map(tasks)},
        bench_pin_value={"tasks_sha256": {}},
    )
    health = summary["data_health"]["by_level"]["L1"]
    _assert(health["zero_step_tasks"] == 2, "two repetition tasks all zero-step")
    _assert(health["empty_response_tasks"] == 2, "two repetition tasks all empty-response")


def _task_id_producer(scored_ids, value=1.0):
    def _score(ctx):
        return value if ctx.task_schema.get("task_id") in scored_ids else None

    return _score


def _toy_task(task_id):
    return {
        "task_id": task_id,
        "level": 1,
        "golden_action": [],
        "tool_calls": [],
    }


def _with_level_specs(level, specs, callback):
    original = score_run.LEVEL_SPECS[level]
    score_run.LEVEL_SPECS[level] = specs
    try:
        return callback()
    finally:
        score_run.LEVEL_SPECS[level] = original


def test_average_metric_records_n_tasks_for_scored_values():
    tasks = [_toy_task("score-me"), _toy_task("skip-me")]
    spec = score_run.MetricSpec("Toy", _task_id_producer({"score-me"}), True)
    entry = score_run._average_metric(tasks, spec)
    _assert_close(entry["score"], 1.0, "toy metric score")
    _assert(entry["n_tasks"] == 1, "n_tasks counts scored tasks")


def test_score_level_scored_tasks_matches_total_when_all_metrics_score_all_tasks():
    tasks = [_l2_task("L2-scored-all-1", "A"), _l2_task("L2-scored-all-2", "A")]
    summary = score_run.score_level("L2", {"results": tasks}, _bench_map(tasks))
    _assert(summary["scored_tasks"] == summary["total"], "scored_tasks should match total")


def test_score_level_scored_tasks_uses_union_across_in_score_metrics():
    tasks = [_toy_task("task-1"), _toy_task("task-2"), _toy_task("task-3")]
    specs = (
        score_run.MetricSpec("ToyA", _task_id_producer({"task-1", "task-2"}), True),
        score_run.MetricSpec("ToyB", _task_id_producer({"task-2", "task-3"}), True),
    )

    def _run():
        return score_run.score_level("L1", {"results": tasks}, _bench_map(tasks))

    summary = _with_level_specs("L1", specs, _run)
    _assert(summary["metrics"]["ToyA"]["n_tasks"] == 2, "ToyA individual count")
    _assert(summary["metrics"]["ToyB"]["n_tasks"] == 2, "ToyB individual count")
    _assert(summary["scored_tasks"] == 3, "scored_tasks must be union count")


def test_agent_score_weights_by_scored_tasks_not_total():
    l1_tasks = [_toy_task("L1-score-1"), _toy_task("L1-score-2"), _toy_task("L1-skip-3")]
    l2_tasks = [_toy_task("L2-score-1")]
    specs_l1 = (score_run.MetricSpec("ToyL1", _task_id_producer({"L1-score-1", "L1-score-2"}), True),)
    specs_l2 = (score_run.MetricSpec("ToyL2", _task_id_producer({"L2-score-1"}, 0.0), True),)
    original_l1 = score_run.LEVEL_SPECS["L1"]
    original_l2 = score_run.LEVEL_SPECS["L2"]
    score_run.LEVEL_SPECS["L1"] = specs_l1
    score_run.LEVEL_SPECS["L2"] = specs_l2
    try:
        summary = score_run.build_summary_from_loaded_for_test(
            {"L1": {"results": l1_tasks}, "L2": {"results": l2_tasks}},
            Path("/tmp/results/x/t/language/agent"),
            bench_task_maps={"L1": _bench_map(l1_tasks), "L2": _bench_map(l2_tasks)},
            bench_pin_value={"tasks_sha256": {}},
        )
    finally:
        score_run.LEVEL_SPECS["L1"] = original_l1
        score_run.LEVEL_SPECS["L2"] = original_l2

    scored_weighted = (1.0 * 2 + 0.0 * 1) / 3
    total_weighted = (1.0 * 3 + 0.0 * 1) / 4
    _assert(summary["by_level"]["L1"]["total"] == 3, "L1 total")
    _assert(summary["by_level"]["L1"]["scored_tasks"] == 2, "L1 scored_tasks")
    _assert_close(summary["agent_score"], scored_weighted, "scored task weighted score")
    _assert(summary["agent_score"] != total_weighted, "must differ from total weighting")


def test_weighting_excludes_level_with_zero_scored_tasks():
    l1_tasks = [_toy_task("L1-unscored-1"), _toy_task("L1-unscored-2")]
    l2_tasks = [_toy_task("L2-scored-1")]
    specs_l1 = (score_run.MetricSpec("ToyL1", _task_id_producer(set()), True),)
    specs_l2 = (score_run.MetricSpec("ToyL2", _task_id_producer({"L2-scored-1"}), True),)
    original_l1 = score_run.LEVEL_SPECS["L1"]
    original_l2 = score_run.LEVEL_SPECS["L2"]
    score_run.LEVEL_SPECS["L1"] = specs_l1
    score_run.LEVEL_SPECS["L2"] = specs_l2
    try:
        summary = score_run.build_summary_from_loaded_for_test(
            {"L1": {"results": l1_tasks}, "L2": {"results": l2_tasks}},
            Path("/tmp/results/x/t/language/agent"),
            bench_task_maps={"L1": _bench_map(l1_tasks), "L2": _bench_map(l2_tasks)},
            bench_pin_value={"tasks_sha256": {}},
        )
    finally:
        score_run.LEVEL_SPECS["L1"] = original_l1
        score_run.LEVEL_SPECS["L2"] = original_l2

    _assert(summary["by_level"]["L1"]["total"] == 2, "L1 total remains task count")
    _assert(summary["by_level"]["L1"]["scored_tasks"] == 0, "L1 scored_tasks zero")
    _assert("L1" not in summary["weighting"]["weights"], "zero-scored level excluded")
    _assert(summary["weighting"]["weights"] == {"L2": 1}, "only scored level weighted")


def test_weighting_scheme_is_scored_task_count():
    tasks = [_toy_task("L1-scheme")]
    specs = (score_run.MetricSpec("Toy", _task_id_producer({"L1-scheme"}), True),)

    def _run():
        return score_run.build_summary_from_loaded_for_test(
            {"L1": {"results": tasks}},
            Path("/tmp/results/x/t/language/agent"),
            bench_task_maps={"L1": _bench_map(tasks)},
            bench_pin_value={"tasks_sha256": {}},
        )

    summary = _with_level_specs("L1", specs, _run)
    _assert(summary["weighting"]["scheme"] == "scored_task_count", "weighting scheme")


def test_record_only_metrics_do_not_contribute_to_scored_tasks():
    tasks = [_toy_task("task-1"), _toy_task("task-2"), _toy_task("task-3")]
    specs = (
        score_run.MetricSpec("ToyInScore", _task_id_producer({"task-1"}), True),
        score_run.MetricSpec("ToyRecordOnly", _task_id_producer({"task-1", "task-2", "task-3"}), False),
    )

    def _run():
        return score_run.score_level("L1", {"results": tasks}, _bench_map(tasks))

    summary = _with_level_specs("L1", specs, _run)
    _assert(summary["metrics"]["ToyInScore"]["n_tasks"] == 1, "in_score n_tasks")
    _assert(summary["metrics"]["ToyRecordOnly"]["n_tasks"] == 3, "record-only n_tasks")
    _assert(summary["scored_tasks"] == 1, "record-only must not affect scored_tasks")


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
    test_golden_field_recall_happy_path,
    test_golden_field_recall_partial,
    test_golden_field_recall_seeded_echo_zero,
    test_golden_field_recall_html_tags_expected_and_response,
    test_golden_field_recall_category_arrows_preserved,
    test_golden_field_recall_numeric_comma_match,
    test_golden_field_recall_description_contents_filtered,
    test_golden_field_recall_unresolved_excluded_from_denominator,
    test_l6_resolve_field_with_fallback_exact_wins,
    test_l6_resolve_field_with_fallback_unique_list_leaf,
    test_l6_resolve_field_with_fallback_ambiguous_unresolved,
    test_l6_resolve_field_with_fallback_scalar_suffix,
    test_l6_golden_field_diagnostics_counts_fallback_fields,
    test_golden_field_recall_evaluation_turn_boundary,
    test_no_refetch_det_empty_action_trace,
    test_no_refetch_det_any_call_including_failed,
    test_l6_refetch_with_correct_answer_not_full_score,
    test_l6_no_refetch_with_correct_answer_full_score,
    test_l4_meaningful_result_predicate,
    test_l4_stock_trades_empty_payload_not_meaningful,
    test_l4_stock_quote_shape_meaningful,
    test_l4_coverage_det_recovers_non_search_shape,
    test_l4_source_epr_det_counts_meaningful_calls,
    test_l4_spec_shape_and_passk_primary,
    test_l4_change_leaves_l6_and_l3_shapes_unchanged,
    test_l6_spec_shape_and_passk_primary,
    test_l3_spec_shape,
    test_l3_passk_primary_resolves_to_spec,
    test_l3_representative_score_excludes_fsm_strict,
    test_l2_spec_shape,
    test_l2_passk_primary_resolves_to_spec,
    test_l2_correct_tool_wrong_args_not_full_score,
    test_other_level_shapes_unchanged,
    test_agent_score_scored_task_count_weighting_differs_from_equal_mean,
    test_agent_score_excludes_none_score_from_weighting,
    test_agent_score_no_scores_has_empty_weights,
    test_data_health_no_tool_calls_warns,
    test_data_health_tool_calls_no_warning,
    test_data_health_counts_repetition_record_tool_calls,
    test_data_health_empty_repetition_records_falls_back_to_parent,
    test_data_health_by_level_counts_loaded_levels,
    test_data_health_l6_fallback_key_and_non_l6_l3_absent,
    test_data_health_l3_prefix_only_tasks,
    test_l6_data_health_load_guard,
    test_l6_data_health_field_diagnostics_and_non_l6_shape,
    test_data_health_empty_run_not_parser_warning,
    test_data_health_counts_zero_step_tasks,
    test_data_health_missing_steps_taken_counts_zero,
    test_data_health_counts_empty_response_tasks,
    test_data_health_new_keys_on_non_special_level_and_score_unchanged,
    test_data_health_rollup_sums_levels,
    test_data_health_repetition_records_zero_step_and_empty_response,
    test_average_metric_records_n_tasks_for_scored_values,
    test_score_level_scored_tasks_matches_total_when_all_metrics_score_all_tasks,
    test_score_level_scored_tasks_uses_union_across_in_score_metrics,
    test_agent_score_weights_by_scored_tasks_not_total,
    test_weighting_excludes_level_with_zero_scored_tasks,
    test_weighting_scheme_is_scored_task_count,
    test_record_only_metrics_do_not_contribute_to_scored_tasks,
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
