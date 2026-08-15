from _harness import *
from pathlib import Path

def test_repetition_record_shape_helper_rules():
    parent = {
        "task_id": "shape-parent",
        "tool_calls": [{"tool_name": "A"}],
    }
    _assert(
        score_run._has_repetition_records({**parent, "repetition_records": [{"rep_index": 0}]})
        is True,
        "non-empty repetition_records list is recognized",
    )
    for records, message in (
        ([], "empty repetition_records falls back to parent"),
        (None, "missing repetition_records falls back to parent"),
        ("not-a-list", "non-list repetition_records falls back to parent"),
    ):
        task = dict(parent)
        if records is not None:
            task["repetition_records"] = records
        _assert(score_run._has_repetition_records(task) is False, message)
        _assert(data_health._tool_call_count(task) == 1, message)



def test_score_run_and_data_health_share_repetition_record_helper():
    _assert(
        score_run._has_repetition_records is data_health._has_repetition_records,
        "score_run and data_health must import the identical helper",
    )

def test_data_health_no_tool_calls_warns():
    l6_tasks = [
        _l6_no_call_task("L6-health-empty-1"),
        _l6_no_call_task("L6-health-empty-2"),
    ]
    summary = score_run.build_summary_from_loaded(
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
    summary = score_run.build_summary_from_loaded(
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
    summary = score_run.build_summary_from_loaded(
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
    summary = score_run.build_summary_from_loaded(
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
    summary = score_run.build_summary_from_loaded(
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
    summary = score_run.build_summary_from_loaded(
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
    summary = score_run.build_summary_from_loaded(
        {"L3": {"results": [prefix_task, exact_task]}},
        Path("/tmp/results/x/t/language/agent"),
        bench_task_maps={"L3": _bench_map([prefix_task, exact_task])},
        bench_pin_value={"tasks_sha256": {}},
    )
    by_level = summary["data_health"]["by_level"]
    _assert(by_level["L3"]["prefix_only_tasks"] == 1, "one prefix-only L3 task")
    _assert(
        data_health._l3_data_health([exact_task], _bench_map([exact_task]))["prefix_only_tasks"] == 0,
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
        health = data_health._l6_data_health([task], None)
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
    summary = score_run.build_summary_from_loaded(
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
    summary = score_run.build_summary_from_loaded(
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
    summary = score_run.build_summary_from_loaded(
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
    summary = score_run.build_summary_from_loaded(
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
    summary = score_run.build_summary_from_loaded(
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
    summary = score_run.build_summary_from_loaded(
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
    summary = score_run.build_summary_from_loaded(
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
    summary = score_run.build_summary_from_loaded(
        {"L1": {"results": tasks}},
        Path("/tmp/results/x/t/language/agent"),
        bench_task_maps={"L1": _bench_map(tasks)},
        bench_pin_value={"tasks_sha256": {}},
    )
    health = summary["data_health"]["by_level"]["L1"]
    _assert(health["zero_step_tasks"] == 2, "two repetition tasks all zero-step")
    _assert(health["empty_response_tasks"] == 2, "two repetition tasks all empty-response")



TESTS = [
    test_repetition_record_shape_helper_rules,
    test_score_run_and_data_health_share_repetition_record_helper,
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
]
