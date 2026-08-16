from pathlib import Path

from _harness import _assert, _load_module_from_path


AGENT_DIR = Path(__file__).resolve().parents[2]
result_records = _load_module_from_path(
    "result_records",
    AGENT_DIR / "gpustack_custom" / "result_records.py",
    str(AGENT_DIR / "gpustack_custom"),
)


def _successful_result():
    return {
        "task_id": "L2-001",
        "instruction": "Find the value",
        "level": 2,
        "category": "lookup",
        "success": True,
        "execution_time": 3.25,
        "steps_taken": 2,
        "error": None,
        "expected_tools": ["Search"],
        "golden_action": [{"tool": "Search", "args": {"q": "value"}}],
        "minimum_steps": 1,
        "data_flow": [{"from": "Search", "to": "response"}],
        "error_injection": {"mode": "none"},
        "fallback_options": [{"tool": "Fallback"}],
        "resp_schema": {"answer": "string"},
        "arg_schema": {"q": "string"},
        "repetitions": 1,
        "repetition_results": [True],
        "token_usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        },
        "ttft_stats": {
            "average": 0.25,
            "min": 0.2,
            "max": 0.3,
            "count": 2,
        },
        "tool_calls": [
            {
                "step": 1,
                "tool_name": "Search",
                "arguments": {"q": "value"},
                "success": True,
                "error": None,
                "result": {"items": [1]},
            },
            {
                "step": 2,
                "tool_name": "Lookup",
                "arguments": {"id": 1},
                "success": False,
                "error": "missing",
                "result": {"ignored": True},
            },
        ],
        "result": {
            "final_response": "answer",
            "conversation": [
                {"role": "user", "content": "Find it"},
                {"role": "assistant", "content": "Calling Search"},
                {
                    "role": "tool",
                    "tool_call_id": "call-1",
                    "content": "{\"items\": [1]}",
                },
            ],
        },
    }


def test_simplify_successful_task_record_exact_shape():
    record = result_records.simplify_result(_successful_result())
    expected = {
        "task_id": "L2-001",
        "instruction": "Find the value",
        "level": 2,
        "category": "lookup",
        "success": True,
        "execution_time": 3.25,
        "steps_taken": 2,
        "error": None,
        "expected_tools": ["Search"],
        "golden_action": [{"tool": "Search", "args": {"q": "value"}}],
        "minimum_steps": 1,
        "data_flow": [{"from": "Search", "to": "response"}],
        "error_injection": {"mode": "none"},
        "fallback_options": [{"tool": "Fallback"}],
        "resp_schema": {"answer": "string"},
        "arg_schema": {"q": "string"},
        "repetitions": 1,
        "repetition_results": [True],
        "token_usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        },
        "ttft_stats": {
            "average": 0.25,
            "min": 0.2,
            "max": 0.3,
            "count": 2,
        },
        "tool_calls": [
            {
                "step": 1,
                "tool_name": "Search",
                "arguments": {"q": "value"},
                "success": True,
                "error": None,
                "result": {"items": [1]},
            },
            {
                "step": 2,
                "tool_name": "Lookup",
                "arguments": {"id": 1},
                "success": False,
                "error": "missing",
            },
        ],
        "final_response": "answer",
        "conversation_log": {
            "total_messages": 3,
            "messages": [
                {"role": "user", "content": "Find it"},
                {"role": "assistant", "content": "Calling Search"},
                {
                    "role": "tool",
                    "tool_call_id": "call-1",
                    "content": {"items": [1]},
                },
            ],
        },
    }
    _assert(record == expected, "successful simplified record shape")
    _assert(list(record) == list(expected), "successful simplified record key order")


def test_repetition_records_and_empty_parent_fallback_shape():
    result = _successful_result()
    result["repetition_records"] = []
    parent_without_records = result_records.simplify_result(result)
    _assert("repetition_records" not in parent_without_records, "empty repetition_records omitted")
    _assert(parent_without_records["tool_calls"], "parent keeps tool_calls for fallback")

    result["repetition_records"] = [{"rep_index": 0, "success": True}]
    parent_with_records = result_records.simplify_result(result)
    _assert(
        parent_with_records["repetition_records"] == [{"rep_index": 0, "success": True}],
        "non-empty repetition_records preserved",
    )
    _assert(parent_with_records["tool_calls"], "parent keeps scorer fields with repetition records")

    rep = result_records.repetition_record(result, 3, seed=1003)
    expected_keys = [
        "rep_index",
        "success",
        "steps_taken",
        "execution_time",
        "error",
        "tool_calls",
        "final_response",
        "conversation_log",
        "token_usage",
        "ttft_stats",
        "seed",
    ]
    _assert(list(rep) == expected_keys, "repetition key order")
    _assert(rep["rep_index"] == 3, "rep_index")
    _assert(rep["seed"] == 1003, "seed")
    _assert(rep["tool_calls"] == parent_with_records["tool_calls"], "repetition tool calls")
    _assert(rep["final_response"] == "answer", "repetition final response")


def test_failed_task_record_shape_and_scorer_fields():
    failure_rep = result_records.failure_repetition_record("boom", 1, seed=1001)
    expected_failure_rep = {
        "rep_index": 1,
        "success": False,
        "steps_taken": 0,
        "execution_time": 0,
        "error": "boom",
        "tool_calls": [],
        "final_response": None,
        "conversation_log": {"total_messages": 0, "messages": []},
        "token_usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
        "ttft_stats": {
            "average": 0,
            "min": 0,
            "max": 0,
            "count": 0,
        },
        "seed": 1001,
    }
    _assert(failure_rep == expected_failure_rep, "failure repetition record shape")

    task = {
        "id": "L3-fail",
        "description": "do it",
        "level": 3,
        "category": "workflow",
        "available_tools": ["A"],
        "golden_action": [{"tool": "A", "args": {}}],
        "minimum_steps": 2,
        "data_flow": ["x"],
    }
    record = result_records.failed_task_record(task, "boom", 3, [True], [failure_rep])
    expected = {
        "task_id": "L3-fail",
        "instruction": "do it",
        "level": 3,
        "category": "workflow",
        "expected_tools": ["A"],
        "golden_action": [{"tool": "A", "args": {}}],
        "minimum_steps": 2,
        "data_flow": ["x"],
        "repetitions": 3,
        "repetition_results": [True, False, False],
        "repetition_records": [failure_rep],
        "success": False,
        "error": "boom",
        "execution_time": 0,
        "steps_taken": 0,
        "tool_invocations": [],
        "tool_calls": [],
    }
    _assert(record == expected, "failed task record shape")
    _assert(record["expected_tools"] == ["A"], "scorer expected_tools present")
    _assert(record["golden_action"] == task["golden_action"], "scorer golden_action present")
    _assert(record["tool_calls"] == [], "scorer tool_calls present")


def test_failed_task_repetition_records_boundary():
    task = {
        "id": "L1-fail",
        "description": "single fail",
        "level": 1,
        "category": "basic",
        "available_tools": ["A"],
        "golden_action": [{"tool": "A", "args": {}}],
    }
    failure_rep = result_records.failure_repetition_record("boom", 0)

    single = result_records.failed_task_record(task, "boom", 1, [], [failure_rep])
    _assert("repetition_records" not in single, "single repetition omits repetition_records key")
    _assert(single["repetition_results"] == [False], "single repetition padding")

    repeated = result_records.failed_task_record(task, "boom", 2, [], [failure_rep])
    _assert("repetition_records" in repeated, "repeated failure includes repetition_records key")
    _assert(repeated["repetition_records"] == [failure_rep], "repeated failure records preserved")
    _assert(repeated["repetition_results"] == [False, False], "repeated failure padding")


def test_token_and_ttft_stats_aggregation():
    first = _successful_result()
    second = _successful_result()
    third = _successful_result()
    first.update({
        "execution_time": 1.111,
        "steps_taken": 2,
        "token_usage": {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30,
        },
        "ttft_stats": {
            "average": 0.12345,
            "min": 0.1,
            "max": 0.2,
            "count": 2,
        },
        "tool_calls": [
            {
                "step": 1,
                "tool_name": "Search",
                "arguments": {},
                "success": True,
                "error": None,
            }
        ],
    })
    second.update({
        "task_id": "L2-002",
        "success": False,
        "execution_time": 2.222,
        "steps_taken": 2,
        "token_usage": {
            "prompt_tokens": 11,
            "completion_tokens": 17,
            "total_tokens": 28,
        },
        "ttft_stats": {
            "average": 0.23456,
            "min": 0.2,
            "max": 0.3,
            "count": 2,
        },
        "tool_calls": [
            {
                "step": 1,
                "tool_name": "Search",
                "arguments": {},
                "success": False,
                "error": "nope",
            },
            {
                "step": 2,
                "tool_name": "Lookup",
                "arguments": {},
                "success": True,
                "error": None,
            }
        ],
    })
    third.update({
        "task_id": "L2-003",
        "execution_time": 3.332,
        "steps_taken": 3,
        "token_usage": {
            "prompt_tokens": 11,
            "completion_tokens": 16,
            "total_tokens": 27,
        },
        "ttft_stats": {
            "average": 0,
            "min": 0,
            "max": 0,
            "count": 0,
        },
        "tool_calls": [
            {
                "step": 1,
                "tool_name": "Search",
                "arguments": {},
                "success": True,
                "error": None,
            },
            {
                "step": 2,
                "tool_name": "Lookup",
                "arguments": {},
                "success": False,
                "error": "nope",
            }
        ],
    })
    log = result_records.build_detailed_results_log(
        [first, second, third],
        "provider/model-name",
        "L2",
        "2026-08-16T00:00:00",
        native_tool_calling=True,
    )
    expected_metadata = {
        "timestamp": "2026-08-16T00:00:00",
        "model": "provider/model-name",
        "level": "L2",
        "native_tool_calling": True,
        "total_tasks": 3,
        "successful_tasks": 2,
        "failed_tasks": 1,
        "success_rate": 66.67,
        "total_execution_time": 6.67,
        "average_execution_time": 2.22,
        "total_steps": 7,
        "average_steps": 2.33,
        "total_tool_calls": 5,
        "average_tool_calls": 1.67,
        "total_tokens": 85,
        "average_tokens_per_task": 28.33,
        "average_prompt_tokens": 10.67,
        "average_completion_tokens": 17.67,
        "average_tps": 12.75,
        "ttft": {
            "average": 0.179,
            "min": 0.1235,
            "max": 0.2346,
            "unit": "seconds",
        },
    }
    _assert(log["metadata"] == expected_metadata, "metadata aggregation and rounding")
    _assert(
        log["tool_usage_statistics"] == {
            "Search": {"count": 3, "success": 2, "failure": 1},
            "Lookup": {"count": 2, "success": 1, "failure": 1},
        },
        "tool usage stats",
    )
    _assert(len(log["results"]) == 3, "simplified results included")


def test_zero_task_stats_aggregation():
    log = result_records.build_detailed_results_log(
        [],
        "model",
        "L1",
        "2026-08-16T00:00:00",
    )
    expected_metadata = {
        "timestamp": "2026-08-16T00:00:00",
        "model": "model",
        "level": "L1",
        "native_tool_calling": False,
        "total_tasks": 0,
        "successful_tasks": 0,
        "failed_tasks": 0,
        "success_rate": 0,
        "total_execution_time": 0,
        "average_execution_time": 0,
        "total_steps": 0,
        "average_steps": 0,
        "total_tool_calls": 0,
        "average_tool_calls": 0,
        "total_tokens": 0,
        "average_tokens_per_task": 0,
        "average_prompt_tokens": 0,
        "average_completion_tokens": 0,
        "average_tps": 0,
        "ttft": {
            "average": 0,
            "min": 0,
            "max": 0,
            "unit": "seconds",
        },
    }
    _assert(log["metadata"] == expected_metadata, "zero-task metadata")
    _assert(log["tool_usage_statistics"] == {}, "zero-task tool stats")
    _assert(log["results"] == [], "zero-task results")


def test_missing_and_none_field_defaults_are_pinned():
    record = result_records.simplify_result({
        "result": {"final_response": "", "conversation": None},
        "tool_calls": [
            {
                "tool_name": "Tool",
                "success": True,
                "result": None,
            }
        ],
        "token_usage": None,
        "ttft_stats": None,
    })
    expected = {
        "task_id": "unknown",
        "instruction": "",
        "level": 0,
        "category": "unknown",
        "success": False,
        "execution_time": 0,
        "steps_taken": 0,
        "error": None,
        "expected_tools": [],
        "golden_action": [],
        "minimum_steps": None,
        "data_flow": [],
        "error_injection": None,
        "fallback_options": [],
        "resp_schema": {},
        "arg_schema": {},
        "repetitions": 1,
        "repetition_results": [],
        "token_usage": None,
        "ttft_stats": None,
        "tool_calls": [
            {
                "step": None,
                "tool_name": "Tool",
                "arguments": None,
                "success": True,
                "error": None,
            }
        ],
        "final_response": None,
        "conversation_log": {"total_messages": 0, "messages": []},
    }
    _assert(record == expected, "missing/default/None field handling")


TESTS = [
    test_simplify_successful_task_record_exact_shape,
    test_repetition_records_and_empty_parent_fallback_shape,
    test_failed_task_record_shape_and_scorer_fields,
    test_failed_task_repetition_records_boundary,
    test_token_and_ttft_stats_aggregation,
    test_zero_task_stats_aggregation,
    test_missing_and_none_field_defaults_are_pinned,
]
