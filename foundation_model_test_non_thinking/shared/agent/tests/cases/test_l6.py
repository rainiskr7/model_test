from _harness import (
    DummyContext,
    MetricContext,
    _assert,
    _assert_close,
    _l6_metric,
    _l6_schema,
    context,
    extra_metrics,
    l6_context,
    level_spec,
    score_run,
)

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
    resolved, value, used_fallback = l6_context.l6_resolve_field_with_fallback(
        result, "data[0].date"
    )
    _assert(resolved is True, "exact path should resolve")
    _assert(value == "exact", "exact value should win")
    _assert(used_fallback is False, "exact resolution must not mark fallback")



def test_l6_resolve_field_with_fallback_unique_list_leaf():
    result = {"chart_data": [{"date": "20250926"}]}
    resolved, value, used_fallback = l6_context.l6_resolve_field_with_fallback(
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
    resolved, value, used_fallback = l6_context.l6_resolve_field_with_fallback(
        result, "data[0].date"
    )
    _assert(resolved is False, "ambiguous fallback should stay unresolved")
    _assert(value is None, "ambiguous fallback must not pick a value")
    _assert(used_fallback is False, "ambiguous fallback must not be marked")



def test_l6_resolve_field_with_fallback_scalar_suffix():
    resolved, value, used_fallback = l6_context.l6_resolve_field_with_fallback(
        {"market_count": 120}, "count"
    )
    _assert(resolved is True, "scalar suffix fallback should resolve")
    _assert(value == 120, "scalar suffix fallback value")
    _assert(used_fallback is True, "scalar suffix fallback should be marked")

    resolved, value, used_fallback = l6_context.l6_resolve_field_with_fallback(
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
    diagnostics = l6_context.l6_golden_field_diagnostics(
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



TESTS = [
    test_l6_empty_tool_calls_not_full_score,
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
    test_l6_spec_shape_and_passk_primary,
]
