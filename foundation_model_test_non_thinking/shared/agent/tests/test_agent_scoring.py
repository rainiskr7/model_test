"""agent scoring 단독 실행 테스트.

패키지 import 없이 파일 경로에서 직접 로드한다.
"""

import ast
import contextlib
import copy
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List


SCORING_DIR = Path(__file__).resolve().parents[1] / "scoring"
TREE_ROOT = Path(__file__).resolve().parents[3]
CUSTOM_DIR = Path(__file__).resolve().parents[1] / "gpustack_custom"
TIMEOUT_CONFIG_PATH = (
    CUSTOM_DIR / "runner_timeout_config.py"
)
RESULT_OBSERVABILITY_PATH = CUSTOM_DIR / "result_observability.py"
RUNNER_PATH = CUSTOM_DIR / "run_gpustack_benchmark_with_logging.py"
REPORT_SCRIPT = TREE_ROOT.parent / "report_agent_levels.sh"
FRESH_RESULTS_SCRIPT = TREE_ROOT.parent / "check_results_fresh.sh"
REPORT_LEVELS = ("L1", "L2", "L3", "L4", "L5", "L6")


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
cache_diagnostics = _load_module("cache_diagnostics")
level_spec = _load_module("level_spec")
aggregate = _load_module("aggregate")
score_run = _load_module("score_run")
validate_run = _load_module("validate_run")
scoring_context = _load_module("context")
task_data = _load_module("task_data")

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


def _load_runner_helpers():
    """Load pure runner helpers without importing optional benchmark dependencies."""
    parsed = ast.parse(RUNNER_PATH.read_text(encoding="utf-8"), filename=str(RUNNER_PATH))
    wanted = {"convert_dataset_to_tasks", "simplify_result"}
    functions = [
        node
        for node in parsed.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in wanted
    ]
    namespace = {
        "Any": Any,
        "Dict": Dict,
        "List": List,
        "json": json,
        "completion_latency_from_task": result_observability.completion_latency_from_task,
        "finish_reason_fields": result_observability.finish_reason_fields,
    }
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(RUNNER_PATH), "exec"), namespace)
    return namespace


runner_helpers = _load_runner_helpers()


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


def test_conversion_preserves_source_tools_and_keeps_required_tools():
    source = {
        "task_id": "L2-test",
        "golden_action": [{"tool": "GoldenTool", "args": {}}],
        "available_tools": ["DistractorTool", "GoldenTool"],
        "conversation_tracking": {
            "turns": [{"action": {"tool": "HistoryTool", "args": {}}}]
        },
        "fallback_options": [{"tool": "FallbackTool"}],
    }
    converted = runner_helpers["convert_dataset_to_tasks"]([source])[0]
    _assert(
        converted["available_tools"]
        == ["GoldenTool", "HistoryTool", "DistractorTool", "FallbackTool"],
        "conversion dropped or reordered an exposed tool",
    )
    _assert(converted["tools"] == converted["available_tools"], "tools alias mismatch")
    _assert(
        converted["expected_tools"] == ["GoldenTool", "HistoryTool"],
        "legacy expected tool set changed",
    )


def test_conversion_without_source_available_tools_keeps_legacy_exposure():
    source = {
        "task_id": "L3-test",
        "golden_action": [{"tool": "FirstTool"}, {"tool": "SecondTool"}],
        "conversation_tracking": {
            "turns": [{"actions": [{"tool": "HistoryTool"}]}]
        },
    }
    converted = runner_helpers["convert_dataset_to_tasks"]([source])[0]
    legacy_tools = ["FirstTool", "SecondTool", "HistoryTool"]
    _assert(converted["available_tools"] == legacy_tools, "legacy exposure changed")
    _assert(converted["expected_tools"] == legacy_tools, "legacy expected tools changed")


def test_simplified_artifact_records_exposed_candidate_set():
    simplified = runner_helpers["simplify_result"](
        {
            "expected_tools": ["GoldenTool"],
            "exposed_tools": ["GoldenTool", "DistractorA", "DistractorB"],
        }
    )
    _assert(simplified["expected_tools"] == ["GoldenTool"], "expected_tools changed")
    _assert(len(simplified["exposed_tools"]) == 3, "exposed candidate count was not saved")


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


def _validation_summary_with_v3():
    summary = _validation_summary()
    v3_by_level = copy.deepcopy(summary["by_level"])
    l6_metrics = v3_by_level["L6"]["metrics"]
    for name in ("ToolAcc", "RedundantCallRate"):
        del l6_metrics[name]
    for name in ("RefetchAvoidance_det", "SeededFieldRecall_det"):
        l6_metrics[name] = {
            "score": 0.6,
            "status": "ok",
            "in_score": True,
            "n_tasks": 1,
            "n_scored": 1,
            "n_errors": 0,
            "task_spread": _task_spread(0.6),
        }
    summary["scoring_v3"] = {
        "scoring_version": aggregate.SCORING_VERSION_V3,
        "agent_score": 0.35,
        "scored_levels": 6,
        "required_levels": 6,
        "agent_score_status": "complete",
        "by_level": v3_by_level,
        "levels_missing": [],
        "levels_unscorable": ["L7"],
        "task_data": {
            "golden_fields_source": "artifact",
            "join_needed": False,
            "benchmark_sha": "1174fedd9fa1c7177baa0cbff039a765c9b14d02",
            "task_file": None,
            "task_file_sha256": None,
            "tasks_joined": 0,
        },
    }
    return summary


def _validation_summary_with_v4():
    summary = _validation_summary_with_v3()
    v4_by_level = copy.deepcopy(summary["scoring_v3"]["by_level"])
    v4_scores = [
        v4_by_level[level]["score"]
        for level in ("L1", "L2", "L3", "L5", "L6")
    ]
    summary["scoring_v4"] = {
        "scoring_version": aggregate.SCORING_VERSION_V4,
        "agent_score": sum(v4_scores) / len(v4_scores),
        "scored_levels": 5,
        "required_levels": 5,
        "agent_score_status": "complete",
        "headline_levels": ["L1", "L2", "L3", "L5", "L6"],
        "excluded_levels": ["L4"],
        "by_level": v4_by_level,
        "levels_missing": [],
        "levels_unscorable": ["L7"],
        "task_data": copy.deepcopy(summary["scoring_v3"]["task_data"]),
    }
    summary["headline_denominators"] = {
        "agent_det_v2": ["L1", "L2", "L3", "L4", "L5", "L6"],
        "agent_det_v3": ["L1", "L2", "L3", "L4", "L5", "L6"],
        "agent_det_v4": ["L1", "L2", "L3", "L5", "L6"],
    }
    return summary


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


def _scoring_candidate(summary=None):
    candidate = copy.deepcopy(summary or _validation_summary())
    candidate.setdefault("levels_missing", [])
    candidate.setdefault("levels_unscorable", ["L7"])
    return candidate


def _run_score_candidate(results_dir, summary, *extra_argv):
    original_bootstrap = score_run.load_metrics_module
    original_build = score_run.build_summary
    score_run.load_metrics_module = lambda: object()
    score_run.build_summary = lambda _results_dir: copy.deepcopy(summary)
    output = io.StringIO()
    try:
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            exit_code = score_run.main(
                ["--results-dir", str(results_dir), *extra_argv]
            )
    finally:
        score_run.load_metrics_module = original_bootstrap
        score_run.build_summary = original_build
    return exit_code, output.getvalue()


def _cache_miss_call(tool_name, arguments):
    return {
        "tool_name": tool_name,
        "arguments": arguments,
        "success": False,
        "error": (
            f"Pseudo-API(read): cache miss for {tool_name} with key=missing. "
            "Seed the cache first."
        ),
    }


def _write_cache_record(cache_dir, tool_name, args, spec, signature=None):
    signature = signature or spec["signature"]
    key = cache_diagnostics.build_cache_key(tool_name, args, signature)
    path = cache_dir / tool_name / key[:2] / f"{key}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "key": key,
                "tool": tool_name,
                "input_params": args,
                "raw_args": args,
                "data": {"fixture": key},
            }
        ),
        encoding="utf-8",
    )
    return key


def _search_spec():
    return cache_diagnostics.make_catalog_entry(
        "POI search",
        {
            "type": "object",
            "properties": {
                "searchKeyword": {"type": "string"},
                "count": {"type": "integer", "default": 10},
                "centerLon": {"type": "number"},
                "centerLat": {"type": "number"},
                "page": {"type": "integer", "default": 1},
            },
            "required": ["searchKeyword"],
        },
    )


def test_cache_classifier_produces_every_bucket_from_hand_built_pairs():
    search_tool = "POISearch_tmap"
    search_spec = _search_spec()
    presentation_tool = "ItemLookup_aladin"
    presentation_spec = cache_diagnostics.make_catalog_entry(
        "item details",
        {
            "type": "object",
            "properties": {
                "item_id": {"type": "string"},
                "item_id_type": {"type": "string", "default": "ISBN13"},
                "cover": {"type": "string", "default": "Mid"},
                "output": {"type": "string", "default": "js"},
                "opt_result": {"type": "string", "default": ""},
            },
        },
    )
    stale_tool = "BlogSearch_naver"
    stale_spec = cache_diagnostics.make_catalog_entry(
        "current blog search",
        {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "display": {"type": "integer", "default": 10},
            },
        },
    )
    no_identity_tool = "SyntheticNoIdentity"
    no_identity_spec = cache_diagnostics.make_catalog_entry(
        "synthetic no-identity tool",
        {"type": "object", "properties": {"mode": {"type": "string"}}},
    )
    absent_tool = "AddressToCoord_kakao"
    absent_spec = cache_diagnostics.make_catalog_entry(
        "address lookup",
        {"type": "object", "properties": {"address": {"type": "string"}}},
    )
    catalog = {
        search_tool: search_spec,
        presentation_tool: presentation_spec,
        stale_tool: stale_spec,
        no_identity_tool: no_identity_spec,
        absent_tool: absent_spec,
    }
    with tempfile.TemporaryDirectory() as temp_dir:
        cache_dir = Path(temp_dir)
        exact_args = {"searchKeyword": "exact", "count": 10, "page": 1}
        _write_cache_record(cache_dir, search_tool, exact_args, search_spec)
        _write_cache_record(
            cache_dir,
            search_tool,
            {
                "searchKeyword": "semantic",
                "count": 10,
                "centerLon": 127.0,
                "centerLat": 37.0,
                "page": 1,
            },
            search_spec,
        )
        _write_cache_record(
            cache_dir,
            presentation_tool,
            {
                "item_id": "9780000000001",
                "item_id_type": "ISBN13",
                "cover": "Mid",
                "output": "js",
                "opt_result": "",
            },
            presentation_spec,
        )
        stale_signature = cache_diagnostics.tool_signature(
            "stale blog search", stale_spec["parameters_schema"]
        )
        _write_cache_record(
            cache_dir,
            stale_tool,
            {"query": "stale", "display": 10},
            stale_spec,
            stale_signature,
        )
        _write_cache_record(cache_dir, no_identity_tool, {"mode": "a"}, no_identity_spec)
        index = cache_diagnostics.load_fixture_index(cache_dir, catalog)

        exact = cache_diagnostics.classify_call(
            {"tool_name": search_tool, "arguments": exact_args}, catalog, index
        )
        presentation = cache_diagnostics.classify_call(
            _cache_miss_call(
                presentation_tool,
                {
                    "item_id": "9780000000001",
                    "cover": "Big",
                    "output": "xml",
                    "opt_result": "Toc,authors",
                },
            ),
            catalog,
            index,
        )
        semantic = cache_diagnostics.classify_call(
            _cache_miss_call(
                search_tool,
                {
                    "searchKeyword": "semantic",
                    "count": 20,
                    "centerLon": 127.0,
                    "centerLat": 37.0,
                    "page": 1,
                },
            ),
            catalog,
            index,
        )
        absent = cache_diagnostics.classify_call(
            _cache_miss_call(search_tool, {"searchKeyword": "absent", "count": 10}),
            catalog,
            index,
        )
        signature = cache_diagnostics.classify_call(
            _cache_miss_call(stale_tool, {"query": "stale", "display": 20}),
            catalog,
            index,
        )
        tool_absent = cache_diagnostics.classify_call(
            _cache_miss_call(absent_tool, {"address": "서울시청"}), catalog, index
        )
        unclassified = cache_diagnostics.classify_call(
            _cache_miss_call(no_identity_tool, {"mode": "b"}), catalog, index
        )

    classified = [
        exact,
        presentation,
        semantic,
        absent,
        signature,
        tool_absent,
        unclassified,
    ]
    expected = list(cache_diagnostics.BUCKETS)
    actual = [entry["bucket"] for entry in classified]
    _assert(actual == expected, f"ordered partition mismatch: {actual}")
    counts = cache_diagnostics._summarize_classifications(classified)["counts"]
    miss_counts = cache_diagnostics._summarize_classifications(classified)["miss_counts"]
    _assert(sum(counts.values()) == len(classified), "bucket counts lost a call")
    _assert(sum(miss_counts.values()) == len(classified) - 1, "miss partition lost a call")
    _assert(all(counts[bucket] == 1 for bucket in expected), "partition is not total")
    _assert(absent["bucket"] != tool_absent["bucket"], "tool/query absence collapsed")


def test_cache_classifier_size_and_count_are_semantic():
    search_spec = _search_spec()
    size_spec = cache_diagnostics.make_catalog_entry(
        "web search",
        {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "sort": {"type": "string", "default": "accuracy"},
                "page": {"type": "integer", "default": 1},
                "size": {"type": "integer", "default": 10},
            },
        },
    )
    catalog = {"POISearch_tmap": search_spec, "WebSearch_daum": size_spec}
    with tempfile.TemporaryDirectory() as temp_dir:
        cache_dir = Path(temp_dir)
        _write_cache_record(
            cache_dir,
            "POISearch_tmap",
            {"searchKeyword": "cafe", "count": 10, "page": 1},
            search_spec,
        )
        _write_cache_record(
            cache_dir,
            "WebSearch_daum",
            {"query": "cache", "sort": "accuracy", "page": 1, "size": 10},
            size_spec,
        )
        index = cache_diagnostics.load_fixture_index(cache_dir, catalog)
        search = cache_diagnostics.classify_call(
            _cache_miss_call(
                "POISearch_tmap", {"searchKeyword": "cafe", "count": 20}
            ),
            catalog,
            index,
        )
        sized = cache_diagnostics.classify_call(
            _cache_miss_call("WebSearch_daum", {"query": "cache", "size": 20}),
            catalog,
            index,
        )
    _assert(search["bucket"] == "semantic_mismatch", "search count stayed presentation")
    _assert(sized["bucket"] == "semantic_mismatch", "search size stayed presentation")


def test_cache_classifier_presentation_fields_are_contract_pinned():
    # Pinned catalog contract: cover only selects image size, output only selects
    # XML/JSON encoding, and opt_result only adds response fields. None can alter
    # entity membership or cardinality.
    _assert(
        cache_diagnostics.PRESENTATION_FIELDS
        == {
            "ItemSearch_aladin": frozenset({"cover", "output", "opt_result"}),
            "ItemList_aladin": frozenset({"cover", "output"}),
            "ItemLookup_aladin": frozenset({"cover", "output", "opt_result"}),
        },
        "presentation map widened without contract review",
    )


def test_cache_classifier_non_text_identity_is_semantic_not_unclassified():
    tool = "StockChart_kis"
    spec = cache_diagnostics.make_catalog_entry(
        "stock chart",
        {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "period": {"type": "string", "default": "D"},
                "count": {"type": "integer", "default": 30},
            },
        },
    )
    catalog = {tool: spec}
    with tempfile.TemporaryDirectory() as temp_dir:
        cache_dir = Path(temp_dir)
        _write_cache_record(
            cache_dir, tool, {"symbol": "005930", "period": "D", "count": 30}, spec
        )
        index = cache_diagnostics.load_fixture_index(cache_dir, catalog)
        result = cache_diagnostics.classify_call(
            _cache_miss_call(tool, {"symbol": "005930", "count": 60}),
            catalog,
            index,
        )
    _assert(result["bucket"] == "semantic_mismatch", "ID identity was unclassified")


def test_cache_classifier_collision_tie_break_is_deterministic():
    tool = "POISearch_tmap"
    spec = _search_spec()
    catalog = {tool: spec}
    with tempfile.TemporaryDirectory() as temp_dir:
        cache_dir = Path(temp_dir)
        keys = [
            _write_cache_record(
                cache_dir,
                tool,
                {"searchKeyword": "collision", "count": count, "page": 1},
                spec,
            )
            for count in (5, 10)
        ]
        index = cache_diagnostics.load_fixture_index(cache_dir, catalog)
        call = _cache_miss_call(tool, {"searchKeyword": "collision", "count": 20})
        selected = [
            cache_diagnostics.classify_call(call, catalog, index)["fixture_key"]
            for _ in range(20)
        ]
    _assert(selected == [min(keys)] * 20, "fixture collision did not use lowest key")


def test_cache_diagnostic_does_not_change_v2_or_v3_headline_bytes():
    summary = _validation_summary_with_v3()
    before = json.dumps(
        {
            "v2": summary["agent_score"],
            "v3": summary["scoring_v3"]["agent_score"],
        },
        separators=(",", ":"),
    ).encode()
    summary["cache_miss_diagnostics"] = cache_diagnostics.build_cache_diagnostics(
        {}, Path("/benchmark-not-present"), catalog={}, fixture_index={}
    )
    after = json.dumps(
        {
            "v2": summary["agent_score"],
            "v3": summary["scoring_v3"]["agent_score"],
        },
        separators=(",", ":"),
    ).encode()
    _assert(before == after, "diagnostic block changed a v2/v3 headline byte")


def _synthetic_l3_mid_miss_task():
    return {
        "task_id": "L3-retry",
        "golden_fields": [],
        "golden_action": [{"tool": "A"}, {"tool": "B"}],
        "tool_calls": [
            _cache_miss_call("A", {"query": "one"}),
            _cache_miss_call("A", {"query": "one"}),
            _cache_miss_call("A", {"query": "two"}),
            {"tool_name": "B", "arguments": {}, "success": True, "error": None},
        ],
    }


def _build_score_neutral_diagnostic_summary(l3_tasks=None, l5_tasks=None):
    original_score_level = aggregate.score_level
    original_score_with_specs = aggregate._score_level_with_specs
    original_prepare_v3 = aggregate.prepare_v3_loaded

    def fake_level(_level, data, *_args):
        return {
            "total": len(data.get("results", [])) or 1,
            "score": data["score"],
            "applied_metrics": 0,
            "metrics": {},
        }

    aggregate.score_level = fake_level
    aggregate._score_level_with_specs = fake_level
    aggregate.prepare_v3_loaded = lambda loaded: (
        loaded,
        {
            "golden_fields_source": "artifact",
            "join_needed": False,
            "benchmark_sha": None,
            "task_file": None,
            "task_file_sha256": None,
            "tasks_joined": 0,
        },
    )
    try:
        loaded = {
            level: {
                "score": index / 10.0,
                "results": (
                    l3_tasks or []
                    if level == "L3"
                    else l5_tasks or []
                    if level == "L5"
                    else []
                ),
            }
            for index, level in enumerate(aggregate.SCORABLE_LEVELS, start=1)
        }
        return aggregate.build_summary_from_loaded(
            loaded, Path("/tmp/results/x/t/language/agent")
        )
    finally:
        aggregate.score_level = original_score_level
        aggregate._score_level_with_specs = original_score_with_specs
        aggregate.prepare_v3_loaded = original_prepare_v3


def test_l3_retry_inflation_mid_miss_counts_and_ratio():
    original_context = aggregate.build_eval_context
    aggregate.build_eval_context = lambda task: task
    try:
        diagnostic = aggregate._build_l3_retry_inflation(
            {"results": [_synthetic_l3_mid_miss_task()]}
        )
    finally:
        aggregate.build_eval_context = original_context
    classes = diagnostic["classes"]
    mid = classes["cache_miss_before_final_call"]
    _assert(mid["tasks"] == 1, "mid-sequence miss task was not classified")
    _assert(mid["calls_emitted"] == 4, "emitted-call count mismatch")
    _assert(mid["golden_action_calls"] == 2, "golden action length mismatch")
    _assert_close(mid["inflation_ratio"], 2.0, "mid-miss inflation ratio")
    _assert(
        diagnostic["after_non_final_miss"]
        == {
            "misses_with_following_call": 3,
            "same_tool_identical_arguments": 1,
            "same_tool_different_arguments": 1,
            "different_tool": 1,
        },
        "post-miss action classes mismatch",
    )
    _assert(
        diagnostic["context_construction_failures"] == {"count": 0},
        "clean L3 task reported a context construction failure",
    )


def test_l3_retry_inflation_reports_context_construction_failures():
    original_context = aggregate.build_eval_context

    def broken_context(_task):
        raise LookupError("L3 context unavailable")

    aggregate.build_eval_context = broken_context
    try:
        diagnostic = aggregate._build_l3_retry_inflation(
            {"results": [_synthetic_l3_mid_miss_task()]}
        )
    finally:
        aggregate.build_eval_context = original_context

    _assert(
        diagnostic["context_construction_failures"]
        == {"count": 1, "error": "LookupError: L3 context unavailable"},
        "L3 context construction failure was laundered",
    )
    _assert(
        sum(entry["tasks"] for entry in diagnostic["classes"].values()) == 1,
        "L3 context failure changed the raw-call retry classification",
    )


def test_l3_retry_inflation_zero_calls_are_separate_from_one_x_baseline():
    no_miss_task = {
        "golden_action": [{"tool": "A"}, {"tool": "B"}],
        "tool_calls": [
            {"tool_name": "A", "arguments": {}, "success": True},
            {"tool_name": "B", "arguments": {}, "success": True},
        ],
    }
    zero_call_task = {
        "golden_action": [{"tool": "A"}, {"tool": "B"}],
        "tool_calls": [],
    }
    classes = aggregate._build_l3_retry_inflation(
        {"results": [no_miss_task, zero_call_task]}
    )["classes"]
    no_miss = classes["no_cache_miss"]
    _assert(no_miss["tasks"] == 1, "no-miss task was not classified")
    _assert(no_miss["calls_emitted"] == 2, "zero-call task entered baseline")
    _assert(no_miss["golden_action_calls"] == 2, "baseline denominator drift")
    _assert_close(no_miss["inflation_ratio"], 1.0, "no-miss inflation ratio")
    zero_calls = classes["no_tool_calls_emitted"]
    _assert(zero_calls["tasks"] == 1, "zero-call task was not separated")
    _assert(zero_calls["calls_emitted"] == 0, "zero-call numerator mismatch")
    _assert(zero_calls["golden_action_calls"] == 2, "zero-call golden mismatch")
    _assert(zero_calls["inflation_ratio"] is None, "zero-call ratio is comparable")


def test_l3_retry_inflation_four_classes_partition_all_tasks():
    tasks = [
        {"golden_action": [{"tool": "A"}], "tool_calls": []},
        {
            "golden_action": [{"tool": "A"}],
            "tool_calls": [
                {"tool_name": "A", "arguments": {}, "success": True}
            ],
        },
        {
            "golden_action": [{"tool": "A"}],
            "tool_calls": [_cache_miss_call("A", {})],
        },
        _synthetic_l3_mid_miss_task(),
    ]
    classes = aggregate._build_l3_retry_inflation({"results": tasks})["classes"]
    _assert(
        set(classes)
        == {
            "no_tool_calls_emitted",
            "no_cache_miss",
            "cache_miss_only_at_final_call",
            "cache_miss_before_final_call",
        },
        "L3 retry diagnostic does not expose exactly four classes",
    )
    _assert(
        {name: entry["tasks"] for name, entry in classes.items()}
        == {name: 1 for name in classes},
        "synthetic L3 tasks did not land in exactly one class each",
    )
    _assert(
        sum(entry["tasks"] for entry in classes.values()) == len(tasks),
        "L3 retry classes do not partition the level tasks",
    )


def test_l3_retry_diagnostic_is_score_and_headline_neutral():
    summary = _build_score_neutral_diagnostic_summary(
        l3_tasks=[_synthetic_l3_mid_miss_task()]
    )
    _assert(
        summary["l3_retry_inflation"]["classes"][
            "cache_miss_before_final_call"
        ]["tasks"]
        == 1,
        "summary omitted the L3 retry diagnostic",
    )
    _assert_close(summary["by_level"]["L3"]["score"], 0.3, "v2 L3 score")
    _assert_close(
        summary["scoring_v3"]["by_level"]["L3"]["score"], 0.3, "v3 L3 score"
    )
    _assert_close(summary["agent_score"], 0.35, "v2 headline")
    _assert_close(summary["scoring_v3"]["agent_score"], 0.35, "v3 headline")
    _assert_close(summary["scoring_v4"]["agent_score"], 0.34, "v4 headline")


def test_l5_ceiling_reports_observed_max_and_caps():
    original_context = aggregate.build_eval_context
    original_specs = aggregate.LEVEL_SPECS_V3["L5"]
    aggregate.build_eval_context = lambda task: task
    aggregate.LEVEL_SPECS_V3["L5"] = tuple(
        aggregate.MetricSpec(name, lambda task, key=name: task[key], True)
        for name in aggregate.L5_METRIC_CEILINGS
    )
    try:
        diagnostic = aggregate._build_l5_ceiling(
            {
                "results": [
                    {
                        "FallbackSR": 0.25,
                        "AdaptiveRoutingScore": 0.5,
                        "EPR_CVR": 0.25,
                    },
                    {
                        "FallbackSR": 1.0,
                        "AdaptiveRoutingScore": 0.4,
                        "EPR_CVR": 0.5,
                    },
                ]
            }
        )
    finally:
        aggregate.build_eval_context = original_context
        aggregate.LEVEL_SPECS_V3["L5"] = original_specs

    _assert_close(
        diagnostic["metrics"]["FallbackSR"]["observed_max"],
        1.0,
        "FallbackSR observed max",
    )
    for name in ("AdaptiveRoutingScore", "EPR_CVR"):
        _assert_close(
            diagnostic["metrics"][name]["observed_max"],
            0.5,
            f"{name} observed max",
        )
        _assert_close(
            diagnostic["metrics"][name]["structural_ceiling"],
            0.5,
            f"{name} structural cap",
        )
    _assert_close(diagnostic["level_ceiling"], 2 / 3, "L5 level ceiling")
    _assert(
        diagnostic["context_construction_failures"] == {"count": 0},
        "clean L5 tasks reported context construction failures",
    )
    for name in aggregate.L5_METRIC_CEILINGS:
        _assert(
            diagnostic["metrics"][name]["producer_failures"] == {"count": 0},
            f"clean {name} evaluations reported producer failures",
        )


def test_l5_ceiling_reports_metric_producer_failure():
    original_context = aggregate.build_eval_context
    original_specs = aggregate.LEVEL_SPECS_V3["L5"]

    def broken_producer(task):
        raise RuntimeError(f"FallbackSR producer unavailable for {task['id']}")

    aggregate.build_eval_context = lambda task: task
    aggregate.LEVEL_SPECS_V3["L5"] = (
        aggregate.MetricSpec("FallbackSR", broken_producer, True),
        aggregate.MetricSpec("AdaptiveRoutingScore", lambda task: 0.5, True),
        aggregate.MetricSpec("EPR_CVR", lambda task: 0.5, True),
    )
    try:
        diagnostic = aggregate._build_l5_ceiling(
            {"results": [{"id": "first"}, {"id": "second"}]}
        )
    finally:
        aggregate.build_eval_context = original_context
        aggregate.LEVEL_SPECS_V3["L5"] = original_specs

    failures = diagnostic["metrics"]["FallbackSR"]["producer_failures"]
    _assert(
        failures
        == {
            "count": 2,
            "error": "RuntimeError: FallbackSR producer unavailable for first",
        },
        "L5 producer failures did not retain count and first exception",
    )
    _assert(
        diagnostic["metrics"]["FallbackSR"]["observed_max"] is None,
        "all-error L5 metric unexpectedly produced an observed maximum",
    )


def test_l5_ceiling_distinguishes_all_context_failures_from_no_values():
    original_context = aggregate.build_eval_context

    def broken_context(_task):
        raise ImportError("benchmark metrics unavailable")

    aggregate.build_eval_context = broken_context
    try:
        diagnostic = aggregate._build_l5_ceiling({"results": [{}, {}]})
    finally:
        aggregate.build_eval_context = original_context

    _assert(
        all(
            entry["observed_max"] is None
            for entry in diagnostic["metrics"].values()
        ),
        "all-context-error L5 run unexpectedly produced a value",
    )
    _assert(
        diagnostic["context_construction_failures"]
        == {"count": 2, "error": "ImportError: benchmark metrics unavailable"},
        "all-context-error L5 run is indistinguishable from no values",
    )


def test_l5_ceiling_diagnostic_is_score_and_headline_neutral():
    summary = _build_score_neutral_diagnostic_summary()
    _assert_close(summary["l5_ceiling"]["level_ceiling"], 2 / 3, "L5 ceiling")
    _assert_close(summary["by_level"]["L5"]["score"], 0.5, "v2 L5 score")
    _assert_close(
        summary["scoring_v3"]["by_level"]["L5"]["score"], 0.5, "v3 L5 score"
    )
    _assert_close(summary["agent_score"], 0.35, "v2 headline")
    _assert_close(summary["scoring_v3"]["agent_score"], 0.35, "v3 headline")
    _assert_close(summary["scoring_v4"]["agent_score"], 0.34, "v4 headline")


def _timeout_task(execution_time, latency_average=2.0, latency_count=2):
    return {
        "task_id": "timeout-probe",
        "error": None,
        "execution_time": execution_time,
        "completion_latency": {
            "average": latency_average,
            "count": latency_count,
        },
    }


def test_possible_absorbed_request_timeout_reports_positive():
    diagnostic = aggregate._build_possible_absorbed_request_timeouts(
        {
            "L3": {
                "metadata": {"request_timeout": 10},
                "results": [_timeout_task(15.0)],
            }
        }
    )
    _assert(
        diagnostic["positives"]
        == [
            {
                "task_id": "timeout-probe",
                "level": "L3",
                "hidden_time": 11.0,
                "request_timeout": 10.0,
            }
        ],
        f"possible absorbed timeout was not reported: {diagnostic}",
    )
    _assert(
        diagnostic["coverage"]["classifiable_tasks"] == 1,
        "positive task was not classifiable",
    )


def test_possible_absorbed_request_timeout_ignores_below_timeout():
    diagnostic = aggregate._build_possible_absorbed_request_timeouts(
        {
            "L2": {
                "metadata": {"request_timeout": 10},
                "results": [_timeout_task(13.0)],
            }
        }
    )
    _assert(diagnostic["positives"] == [], "below-timeout task was reported")
    _assert(
        diagnostic["coverage"]["classifiable_tasks"] == 1,
        "below-timeout task must remain classifiable",
    )


def test_possible_absorbed_request_timeout_missing_fields_are_unclassifiable():
    missing_timeout = _timeout_task(15.0)
    missing_latency = _timeout_task(15.0)
    missing_latency.pop("completion_latency")
    diagnostic = aggregate._build_possible_absorbed_request_timeouts(
        {
            "L1": {"metadata": {}, "results": [missing_timeout]},
            "L2": {
                "metadata": {"request_timeout": 10},
                "results": [missing_latency],
            },
        }
    )
    coverage = diagnostic["coverage"]
    _assert(coverage["classifiable_tasks"] == 0, "missing fields became negatives")
    _assert(coverage["unclassifiable_tasks"] == 2, "unclassifiable count mismatch")
    _assert(
        coverage["unclassifiable_reasons"]["missing_request_timeout"] == 1,
        "missing timeout was not identified",
    )
    _assert(
        coverage["unclassifiable_reasons"]["missing_completion_latency"] == 1,
        "missing completion latency was not identified",
    )


def _l7_field_distribution(final_response):
    ctx = _result_field_coverage_context(
        final_response,
        golden_fields=[
            {"tool": "Catalog", "fields": ["price", "item[0].title"]}
        ],
        include_second=False,
    )
    task = {"golden_fields": ctx.task_schema["golden_fields"]}
    original_context = aggregate.build_eval_context
    aggregate.build_eval_context = lambda _task: ctx
    try:
        return aggregate._build_l7_partial_coverage({"results": [task]})
    finally:
        aggregate.build_eval_context = original_context


def test_l7_partial_coverage_diagnostic_preserves_partial_entry():
    diagnostic = _l7_field_distribution("Alpha Book is available.")
    _assert(
        diagnostic["distribution"]
        == [{"fields_required": 2, "fields_present": 1, "entry_count": 1}],
        f"partial entry collapsed to zero: {diagnostic['distribution']}",
    )
    _assert(diagnostic["totals"]["partial_entries"] == 1, "partial total missing")
    _assert(diagnostic["totals"]["zero_entries"] == 0, "partial counted as zero")


def test_l7_partial_coverage_diagnostic_reports_complete_entry():
    diagnostic = _l7_field_distribution("Alpha Book costs 1,234 won.")
    _assert(
        diagnostic["distribution"]
        == [{"fields_required": 2, "fields_present": 2, "entry_count": 1}],
        f"complete entry was not reported: {diagnostic['distribution']}",
    )
    _assert(
        diagnostic["totals"]["complete_entries"] == 1,
        "complete total missing",
    )


def test_new_annotation_diagnostics_are_score_and_headline_neutral():
    summary = _build_score_neutral_diagnostic_summary()
    _assert(
        summary["possible_absorbed_request_timeout_diagnostics"][
            "annotation_only"
        ]
        is True,
        "absorbed-timeout diagnostic missing",
    )
    _assert(
        summary["l7_partial_coverage_diagnostics"]["annotation_only"] is True,
        "L7 partial-coverage diagnostic missing",
    )
    for level, expected in zip(aggregate.SCORABLE_LEVELS, (0.1, 0.2, 0.3, 0.4, 0.5, 0.6)):
        _assert_close(summary["by_level"][level]["score"], expected, f"{level} score")
    _assert_close(summary["agent_score"], 0.35, "v2 headline")
    _assert_close(summary["scoring_v3"]["agent_score"], 0.35, "v3 headline")
    _assert_close(summary["scoring_v4"]["agent_score"], 0.34, "v4 headline")


def test_new_diagnostics_round_trip_and_validate():
    summary = _validation_summary_with_v4()
    summary["l3_retry_inflation"] = aggregate._build_l3_retry_inflation(
        {"results": [_synthetic_l3_mid_miss_task()]}
    )
    summary["l5_ceiling"] = aggregate._build_l5_ceiling({"results": []})
    with tempfile.TemporaryDirectory() as temp_dir:
        results_dir = Path(temp_dir)
        _write_validation_fixture(results_dir, summary)
        round_tripped = json.loads(
            (results_dir / "summary.json").read_text(encoding="utf-8")
        )
        failures, _warnings = validate_run.validate_results_dir(results_dir)
    _assert(
        round_tripped["l3_retry_inflation"] == summary["l3_retry_inflation"],
        "L3 diagnostic did not survive JSON round-trip",
    )
    _assert(
        round_tripped["l5_ceiling"] == summary["l5_ceiling"],
        "L5 diagnostic did not survive JSON round-trip",
    )
    _assert(not failures, f"new diagnostic blocks failed validation: {failures}")


def _build_infrastructure_diagnostic_summary():
    original_score_level = aggregate.score_level
    original_score_with_specs = aggregate._score_level_with_specs
    original_prepare_v3 = aggregate.prepare_v3_loaded

    def fake_level(_level, data, *_args):
        scores = [
            task["synthetic_score"]
            for task in data.get("results", [])
            if isinstance(task, dict) and "synthetic_score" in task
        ]
        return {
            "total": len(data.get("results", [])),
            "score": sum(scores) / len(scores) if scores else None,
            "applied_metrics": 1 if scores else 0,
            "metrics": {},
        }

    aggregate.score_level = fake_level
    aggregate._score_level_with_specs = fake_level
    aggregate.prepare_v3_loaded = lambda loaded: (
        loaded,
        {
            "golden_fields_source": "artifact",
            "join_needed": False,
            "benchmark_sha": None,
            "task_file": None,
            "task_file_sha256": None,
            "tasks_joined": 0,
        },
    )
    loaded = {
        "L1": {
            "results": [
                {"task_id": "L1-live", "error": None, "synthetic_score": 1.0},
                {
                    "task_id": "L1-dead",
                    "error": "LLM call failed: TimeoutError: request timed out",
                    "synthetic_score": 0.0,
                },
            ]
        },
        "L2": {
            "results": [
                {"task_id": "L2-live", "error": None, "synthetic_score": 0.4}
            ]
        },
    }
    try:
        return aggregate.build_summary_from_loaded(
            loaded, Path("/tmp/results/model/run/language/agent")
        )
    finally:
        aggregate.score_level = original_score_level
        aggregate._score_level_with_specs = original_score_with_specs
        aggregate.prepare_v3_loaded = original_prepare_v3


def test_infrastructure_error_diagnostic_emits_both_bounds_without_rescoring():
    summary = _build_infrastructure_diagnostic_summary()
    diagnostic = summary["infrastructure_error_diagnostics"]["by_level"]["L1"]
    bounds = diagnostic["score_bounds"]
    _assert_close(summary["scoring_v4"]["by_level"]["L1"]["score"], 0.5, "reported L1 score")
    _assert_close(
        bounds["with_infrastructure_error_tasks_scored_as_zero"],
        0.5,
        "as-scored bound",
    )
    _assert_close(
        bounds["with_infrastructure_error_tasks_excluded"],
        1.0,
        "exclusion bound",
    )
    _assert(
        diagnostic["tasks"]
        == [{"task_id": "L1-dead", "error_class": "TimeoutError"}],
        f"infrastructure error task identity missing: {diagnostic}",
    )


def test_infrastructure_error_diagnostic_clean_level_has_zero_count_no_bounds():
    diagnostic = _build_infrastructure_diagnostic_summary()[
        "infrastructure_error_diagnostics"
    ]["by_level"]["L2"]
    _assert(diagnostic["infrastructure_error_task_count"] == 0, "clean L2 count is not zero")
    _assert(diagnostic["tasks"] == [], "clean L2 lists error tasks")
    _assert("score_bounds" not in diagnostic, "clean L2 emitted contamination bounds")


def _seeded_only_zero_step_task(task_id="L6-seeded-only"):
    return {
        "task_id": task_id,
        "error": None,
        "steps_taken": 0,
        "completion_latency": {"count": 0},
        "token_usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
        "tool_calls": [],
        "conversation_log": {
            "messages": [
                {"role": "user", "content": "seeded prompt"},
                {"role": "tool", "content": {"seeded": True}},
            ]
        },
    }


def test_swallowed_exception_detector_fires_on_seeded_only_zero_step_task():
    diagnostic = aggregate._build_swallowed_exception_diagnostics(
        {"L6": {"results": [_seeded_only_zero_step_task()]}}
    )
    _assert(diagnostic["matching_task_count"] == 1, "seeded-only signature was missed")
    _assert(
        diagnostic["by_level"]["L6"]
        == {"matching_task_count": 1, "task_ids": ["L6-seeded-only"]},
        f"seeded-only task identity missing: {diagnostic}",
    )
    _assert(
        "after at least one successful generated step" in diagnostic["detection_limit"],
        "detector limitation was hidden",
    )


def test_swallowed_exception_detector_ignores_generated_zero_tool_call_l6_task():
    task = _seeded_only_zero_step_task("L6-generated")
    task.update(
        {
            "steps_taken": 1,
            "completion_latency": {"count": 1},
            "token_usage": {
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "total_tokens": 120,
            },
        }
    )
    diagnostic = aggregate._build_swallowed_exception_diagnostics(
        {"L6": {"results": [task]}}
    )
    _assert(diagnostic["matching_task_count"] == 0, "genuine zero-tool-call L6 was flagged")
    _assert(diagnostic["by_level"]["L6"]["task_ids"] == [], "false-positive task ID emitted")


def test_validator_warns_above_cache_threshold_without_failing():
    summary = _validation_summary_with_v3()
    summary["cache_miss_diagnostics"] = {
        "by_level": {
            "L3": {"total_calls": 10, "cache_misses": 3, "miss_rate": 0.3}
        }
    }
    failures, warnings = _validate_fixture(summary)
    _assert(not failures, f"cache warning unexpectedly failed validation: {failures}")
    matching = [warning for warning in warnings if "cache miss rate" in warning]
    _assert(matching, "high cache miss rate did not warn")
    _assert("20%" in matching[0] and "3/10" in matching[0], "warning hides threshold/counts")


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


def test_context_prefers_persisted_exposed_tools_with_legacy_fallback():
    task_schema, _logs = scoring_context.task_to_schema_and_logs(
        {
            "expected_tools": ["GoldenTool"],
            "exposed_tools": ["GoldenTool", "DistractorTool"],
        }
    )
    _assert(
        task_schema["available_tools"] == ["GoldenTool", "DistractorTool"],
        "scoring context ignored exposed_tools",
    )
    legacy_schema, _logs = scoring_context.task_to_schema_and_logs(
        {"expected_tools": ["GoldenTool"]}
    )
    _assert(
        legacy_schema["available_tools"] == ["GoldenTool"],
        "legacy expected_tools fallback changed",
    )


def test_v3_task_data_prefers_persisted_fields_without_join():
    loaded = {"L6": {"results": [{"task_id": "L6-X", "golden_fields": []}]}}
    prepared, provenance = task_data.prepare_v3_loaded(loaded)
    _assert(prepared == loaded, "persisted golden_fields were changed")
    _assert(provenance["join_needed"] is False, "persisted fields triggered join")
    _assert(provenance["golden_fields_source"] == "artifact", "source mismatch")


def test_v3_task_data_join_rejects_missing_and_duplicate_task_ids():
    fixtures = [
        ({"L6": {"results": [{}]}}, "missing task_id"),
        (
            {"L6": {"results": [{"task_id": "L6-X"}, {"task_id": "L6-X"}]}},
            "duplicate task_id",
        ),
    ]
    for loaded, expected in fixtures:
        try:
            task_data.prepare_v3_loaded(loaded)
        except RuntimeError as exc:
            _assert(expected in str(exc), f"wrong task-data join error: {exc}")
        else:
            raise AssertionError(f"task-data join accepted {expected}")


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


def test_refetch_avoidance_empty_one_and_missing_trace():
    empty = DummyContext(action_trace=[], logs={})
    _assert_close(
        extra_metrics.refetch_avoidance_det(empty), 1.0, "empty new-call trace"
    )

    one_call = DummyContext(action_trace=[{"tool": "Lookup"}], logs={})
    _assert_close(
        extra_metrics.refetch_avoidance_det(one_call), 0.0, "one new call"
    )

    missing = DummyContext()
    missing.action_trace = None
    _assert(
        extra_metrics.refetch_avoidance_det(missing) is None,
        "missing trace must be not applicable",
    )


def _seeded_recall_context(
    final_response,
    seed_payload=None,
    golden_fields=None,
    action_trace=None,
    include_refetch=False,
    task_schema=None,
):
    seed_payload = seed_payload or {
        "price": 1234.0,
        "item": [{"title": "Alpha Book", "author": "Beta Writer"}],
    }
    golden_fields = golden_fields or [
        {
            "tool": "Lookup",
            "fields": ["price", "item[0].title", "item[0].author"],
        }
    ]
    messages = [
        {
            "role": "tool",
            "tool_call_id": "seed_call_2_1",
            "name": "Lookup",
            "content": seed_payload,
        }
    ]
    if include_refetch:
        messages.append(
            {
                "role": "tool",
                "tool_call_id": "call_model_1",
                "name": "Lookup",
                "content": {
                    "price": 9999,
                    "item": [{"title": "Wrong Fetch", "author": "Wrong Writer"}],
                },
            }
        )
    schema = {"golden_fields": golden_fields}
    schema.update(task_schema or {})
    return DummyContext(
        action_trace=[] if action_trace is None else action_trace,
        task_schema=schema,
        logs={
            "conversation_log": {"messages": messages},
            "final_response": final_response,
        },
    )


def test_seeded_field_recall_uses_seed_when_refetch_also_exists():
    ctx = _seeded_recall_context(
        "Alpha Book by Beta Writer costs 1,234 won", include_refetch=True
    )
    _assert_close(
        extra_metrics.seeded_field_recall_det(ctx),
        1.0,
        "later model refetch replaced the seed payload",
    )


def test_seeded_field_recall_uses_seed_in_moe_artifact_or_skip():
    artifact = (
        TREE_ROOT
        / "results/qwen_qwen3.5_35b_a3b_fp8/p0verify_20260816/language"
        / "agent_p0verify/L6.json"
    )
    if not artifact.is_file():
        print("SKIP test_seeded_field_recall_uses_seed_in_moe_artifact_or_skip: artifact absent")
        return
    tasks = json.loads(artifact.read_text(encoding="utf-8"))["results"]
    task = next(task for task in tasks if task.get("task_id") == "L6-002")
    seed_payload = next(
        message["content"]
        for message in task["conversation_log"]["messages"]
        if str(message.get("tool_call_id", "")).startswith("seed_call_")
    )
    _assert(task.get("tool_calls"), "MoE hazard fixture lost its new re-fetch")
    _assert(
        task["tool_calls"][0].get("result") != seed_payload,
        "MoE re-fetch no longer differs from the seed payload",
    )
    final_response = " | ".join(
        [
            seed_payload["items"][0]["title"],
            seed_payload["items"][0]["description"],
            seed_payload["items"][1]["title"],
            seed_payload["items"][2]["title"],
        ]
    )
    ctx = DummyContext(
        action_trace=task["tool_calls"],
        task_schema={
            "golden_fields": [
                {
                    "tool": "NewsSearch_naver",
                    "fields": [
                        "items[0].title",
                        "items[0].description",
                        "items[1].title",
                        "items[2].title",
                    ],
                }
            ]
        },
        logs={
            "conversation_log": task["conversation_log"],
            "final_response": final_response,
        },
    )
    _assert_close(
        extra_metrics.seeded_field_recall_det(ctx),
        1.0,
        "MoE artifact resolved against its later re-fetch instead of seed_call_2_1",
    )


def test_seeded_field_recall_all_and_partial():
    all_present = _seeded_recall_context(
        "ALPHA BOOK by beta writer costs 1,234.00 won"
    )
    _assert_close(
        extra_metrics.seeded_field_recall_det(all_present), 1.0, "all seeded values"
    )

    partial = _seeded_recall_context("Alpha Book costs 1,234 won")
    _assert_close(
        extra_metrics.seeded_field_recall_det(partial),
        2 / 3,
        "partial seeded field fraction",
    )


def test_seeded_field_recall_unresolvable_is_not_applicable():
    ctx = _seeded_recall_context(
        "Alpha Book",
        golden_fields=[{"tool": "Lookup", "fields": ["missing.path"]}],
    )
    _assert(
        extra_metrics.seeded_field_recall_det(ctx) is None,
        "unresolvable declaration must be not applicable",
    )
    diagnostics = extra_metrics.seeded_field_recall_diagnostics(ctx)
    _assert(diagnostics["fields_unresolved"] == 1, "unresolved count missing")
    _assert(diagnostics["fields_checked"] == 0, "unresolved field was checked")


def test_seeded_field_recall_excludes_long_text_without_failure():
    long_text = "A nondeterministic free-text description " * 4
    ctx = _seeded_recall_context(
        "Alpha Book",
        seed_payload={"title": "Alpha Book", "description": long_text},
        golden_fields=[
            {"tool": "Lookup", "fields": ["title", "description"]}
        ],
    )
    _assert_close(
        extra_metrics.seeded_field_recall_det(ctx),
        1.0,
        "long free text must not count as a miss",
    )
    diagnostics = extra_metrics.seeded_field_recall_diagnostics(ctx)
    _assert(diagnostics["fields_required"] == 2, "required count mismatch")
    _assert(diagnostics["fields_checked"] == 1, "checked count mismatch")
    _assert(
        diagnostics["fields_excluded_long_text"] == 1,
        "long-text exclusion count mismatch",
    )


def test_l6_freshness_and_minimum_calls_do_not_affect_v3_metrics():
    base = _seeded_recall_context("Alpha Book by Beta Writer costs 1,234 won")
    decorated = _seeded_recall_context(
        "Alpha Book by Beta Writer costs 1,234 won",
        task_schema={"freshness_threshold": "24h", "minimum_calls": 2},
    )
    for spec in level_spec.LEVEL_SPECS_V3["L6"]:
        _assert_close(
            spec.producer(base),
            spec.producer(decorated),
            f"{spec.name} used freshness_threshold or minimum_calls",
        )


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
        {
            "role": "tool",
            "tool_call_id": "seed_call_2_1",
            "name": "Catalog",
            "content": first_result,
        },
    ]
    action_trace = [
        {"tool": "Catalog", "args": {}, "result": first_result},
    ]
    if include_second:
        messages.append(
            {
                "role": "tool",
                "tool_call_id": "seed_call_4_1",
                "name": "Author",
                "content": second_result,
            }
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
                    {
                        "role": "tool",
                        "tool_call_id": "seed_call_2_1",
                        "name": "Lookup",
                        "content": result,
                    }
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


def test_result_field_coverage_unresolved_is_not_applicable():
    ctx = _single_result_field_context("present", "present", "missing.path")
    _assert(
        extra_metrics.result_field_coverage_det(ctx) is None,
        "unresolvable seed payload must be not applicable",
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


def test_result_field_coverage_seed_only_applicability_denominator():
    resolvable = _single_result_field_context("present", "present")
    resolvable.action_trace = []
    target_message = resolvable.logs["conversation_log"]["messages"][0]
    target_message.pop("name")
    target_message["tool_call_id"] = "seed_call_4_1"
    resolvable.logs["conversation_log"]["messages"].insert(
        0,
        {
            "role": "tool",
            "tool_call_id": "seed_call_2_1",
            "content": {"value": "unrelated"},
        },
    )
    resolvable.task_schema["context_tests"] = [
        {
            "turn": 4,
            "expected_action": {"tool": "Lookup", "args": {}},
        }
    ]
    unresolvable = _single_result_field_context("present", "present")
    unresolvable.action_trace = []
    unresolvable.logs["conversation_log"]["messages"][0].pop("name")
    unresolvable.task_schema["context_tests"] = [
        {
            "turn": 5,
            "expected_action": {"tool": "Lookup", "args": {}},
        }
    ]
    spec = next(
        spec
        for spec in level_spec.LEVEL_SPECS["L7"]
        if spec.name == "ResultFieldCoverage_det"
    )
    original_context = aggregate.build_eval_context
    aggregate.build_eval_context = lambda task: task
    try:
        entry = aggregate._average_metric([resolvable, unresolvable], spec)
    finally:
        aggregate.build_eval_context = original_context
    _assert_close(entry["score"], 1.0, "seed-only denominator score")
    _assert(entry["n_tasks"] == 2, "seed-only total task count")
    _assert(entry["n_scored"] == 1, "unmapped seed entered denominator")
    _assert(
        isinstance(entry["n_tasks"], int) and isinstance(entry["n_scored"], int),
        "applicability counts must be integral",
    )
    _assert(entry["in_score"] is False, "L7 coverage must remain record-only")


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


def test_frozen_v2_l6_spec_is_unchanged():
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


def test_v3_l6_spec_is_exactly_two_in_score_metrics():
    specs = level_spec.LEVEL_SPECS_V3["L6"]
    _assert(
        tuple(spec.name for spec in specs)
        == ("RefetchAvoidance_det", "SeededFieldRecall_det"),
        "v3 L6 metric contract mismatch",
    )
    _assert(all(spec.in_score for spec in specs), "both v3 L6 metrics must be in score")
    _assert(
        specs[1].diagnostic_producer.__name__
        == "seeded_field_recall_diagnostics",
        "v3 seeded recall diagnostics are not wired",
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


def _contract_score(specs, ctx, evaluator=None):
    values = []
    for spec in specs:
        if not spec.in_score:
            continue
        value = evaluator(spec, ctx) if evaluator else spec.producer(ctx)
        if value is not None:
            values.append(value)
    return level_spec.mean_or_none(values)


def _nonincrease_property(specs, original, with_identical_new_call, evaluator=None):
    before = _contract_score(specs, original, evaluator)
    after = _contract_score(specs, with_identical_new_call, evaluator)
    return before is not None and after is not None and after <= before


def test_seed_clone_polarity_fails_v2_and_passes_v3():
    original = _seeded_recall_context("Alpha Book by Beta Writer costs 1,234 won")
    cloned = _seeded_recall_context(
        "Alpha Book by Beta Writer costs 1,234 won",
        action_trace=[{"tool": "Lookup", "args": {}, "result": {}}],
        include_refetch=True,
    )

    # Plain-python facsimile of the frozen vendored v2 behavior for this
    # metamorph: ToolAcc rewards the cloned golden-tool call and the published
    # RedundantCallRate yields 1 for the one-call trace.
    def frozen_v2_eval(spec, ctx):
        if spec.name == "ToolAcc":
            return 1.0 if ctx.action_trace else 0.0
        if spec.name == "RedundantCallRate":
            return 1.0 if ctx.action_trace else None
        raise AssertionError(f"unexpected frozen-v2 metric {spec.name}")

    v2_holds = _nonincrease_property(
        level_spec.LEVEL_SPECS["L6"], original, cloned, frozen_v2_eval
    )
    v3_holds = _nonincrease_property(
        level_spec.LEVEL_SPECS_V3["L6"], original, cloned
    )
    print(
        "POLARITY seeded-call clone: "
        f"v2={'PASS' if v2_holds else 'FAIL'} v3={'PASS' if v3_holds else 'FAIL'}"
    )
    _assert(not v2_holds, "frozen v2 unexpectedly satisfies non-increase")
    _assert(v3_holds, "v3 score increased after an identical redundant new call")


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


def test_metric_contract_error_fails_closed_with_diagnostics():
    original_context = aggregate.build_eval_context
    original_specs = aggregate.LEVEL_SPECS["L1"]
    invalid_cases = (
        (-8.0, "out_of_range"),
        (1.4, "out_of_range"),
        (2.0, "out_of_range"),
        (float("nan"), "non_finite"),
        (float("inf"), "non_finite"),
    )

    aggregate.build_eval_context = lambda task: task
    aggregate.LEVEL_SPECS["L1"] = (
        aggregate.MetricSpec("BoundedMetric", lambda task: task["score"], True),
    )
    try:
        for invalid, violation in invalid_cases:
            result = aggregate.score_level(
                "L1",
                {
                    "results": [
                        {"task_id": "bad-task", "score": invalid},
                        {"task_id": "good-task", "score": 1.0},
                    ]
                },
            )
            entry = result["metrics"]["BoundedMetric"]
            _assert(entry["status"] == "contract_error", "contract status mismatch")
            _assert(entry["score"] is None, "contract failure must not publish a mean")
            _assert(result["score"] is None, "contract failure must fail level closed")
            _assert(
                result["unscorable_reason"] == "metric_contract_error",
                "contract failure reason mismatch",
            )
            _assert(entry["n_tasks"] == 2, "contract task count mismatch")
            _assert(entry["n_scored"] == 1, "valid task count mismatch")
            _assert(entry["n_errors"] == 0, "contract failure became producer error")
            _assert(entry["n_contract_errors"] == 1, "contract error count mismatch")
            _assert(
                sum(entry["task_spread"].values()) == entry["n_scored"],
                "task spread must still sum to n_scored",
            )
            _assert(
                entry["score"] != 1.0,
                "offending task was silently dropped and remaining mean published",
            )
            diagnostic = entry["contract_errors"][0]
            _assert(diagnostic["metric"] == "BoundedMetric", "diagnostic metric missing")
            _assert(diagnostic["task_id"] == "bad-task", "diagnostic task id missing")
            _assert(
                diagnostic["raw_value"] == repr(invalid),
                "diagnostic raw repr mismatch",
            )
            _assert(diagnostic["violation"] == violation, "diagnostic reason mismatch")
            if violation == "out_of_range":
                clamped_mean = (min(1.0, max(0.0, invalid)) + 1.0) / 2.0
                _assert(
                    entry["score"] != clamped_mean,
                    "offending value was clamped into the metric mean",
                )
    finally:
        aggregate.build_eval_context = original_context
        aggregate.LEVEL_SPECS["L1"] = original_specs


def test_metric_contract_accepts_unit_interval_boundaries():
    original_context = aggregate.build_eval_context
    aggregate.build_eval_context = lambda task: task
    try:
        entry = aggregate._average_metric(
            [
                {"task_id": "zero", "score": 0.0},
                {"task_id": "one", "score": 1.0},
            ],
            aggregate.MetricSpec("Boundaries", lambda task: task["score"], True),
        )
    finally:
        aggregate.build_eval_context = original_context

    _assert(entry["status"] == "ok", "unit interval boundary was rejected")
    _assert_close(entry["score"], 0.5, "boundary mean")
    _assert(entry["n_scored"] == 2, "boundary scored count mismatch")
    _assert(entry["n_contract_errors"] == 0, "boundary contract count mismatch")
    _assert(
        entry["task_spread"]
        == {"n_perfect": 1, "n_zero": 1, "n_partial": 0},
        "boundary spread mismatch",
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
        "PartialMetric=0.500/partial(applicable=2/3)" in output.getvalue(),
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


def test_record_only_metric_contract_error_fails_level_closed():
    original_context = aggregate.build_eval_context
    original_specs = aggregate.LEVEL_SPECS["L1"]

    aggregate.build_eval_context = lambda task: task
    aggregate.LEVEL_SPECS["L1"] = (
        aggregate.MetricSpec("Good", lambda _task: 0.75, True),
        aggregate.MetricSpec("RecordOnlyInvalid", lambda _task: 1.4, False),
    )
    try:
        result = aggregate.score_level("L1", {"results": [{"task_id": "bad-task"}]})
    finally:
        aggregate.build_eval_context = original_context
        aggregate.LEVEL_SPECS["L1"] = original_specs

    entry = result["metrics"]["RecordOnlyInvalid"]
    _assert(entry["status"] == "contract_error", "record-only contract status mismatch")
    _assert(result["score"] is None, "record-only contract error must fail level closed")
    _assert(
        result["unscorable_reason"] == "metric_contract_error",
        "record-only contract failure reason mismatch",
    )


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
    _assert(
        aggregate.SCORING_VERSION_V3 == "agent_det_v3",
        "v3 scoring version contract mismatch",
    )
    _assert(
        aggregate.SCORING_VERSION_V4 == "agent_det_v4",
        "v4 scoring version contract mismatch",
    )
    _assert(
        aggregate.V4_HEADLINE_LEVELS == ("L1", "L2", "L3", "L5", "L6"),
        "v4 denominator literal changed",
    )
    _assert(
        aggregate.V4_EXCLUDED_LEVELS == ("L4",),
        "v4 excluded-level constant changed",
    )


def _synthetic_v4_matrix(l4_score=0.4, l6_score=0.6):
    scores = {
        "L1": 0.1,
        "L2": 0.2,
        "L3": 0.3,
        "L4": l4_score,
        "L5": 0.5,
        "L6": l6_score,
    }
    return {
        level: {"total": 1, "score": score, "metrics": {}}
        for level, score in scores.items()
    }


def test_v4_requires_exactly_its_five_scorable_levels():
    block = aggregate._build_v4_block(
        _synthetic_v4_matrix(), [], {"join_needed": False}
    )
    _assert(block["agent_score_status"] == "complete", "five scores did not complete v4")
    _assert(block["scored_levels"] == 5, "v4 scored-level count mismatch")

    missing_headline = aggregate._build_v4_block(
        _synthetic_v4_matrix(l6_score=None), [], {"join_needed": False}
    )
    _assert(missing_headline["agent_score"] is None, "missing v4 level produced a headline")
    _assert(
        missing_headline["agent_score_status"] == "incomplete",
        "missing v4 level did not mark it incomplete",
    )


def test_v4_l4_null_does_not_block_and_mean_is_exact():
    block = aggregate._build_v4_block(
        _synthetic_v4_matrix(l4_score=None), [], {"join_needed": False}
    )
    expected = (0.1 + 0.2 + 0.3 + 0.5 + 0.6) / 5
    _assert(block["agent_score_status"] == "complete", "null L4 blocked v4")
    _assert_close(block["agent_score"], expected, "v4 five-level mean")
    _assert(block["by_level"]["L4"]["score"] is None, "v4 matrix hid null L4")


def test_v4_exclusion_is_constant_when_l4_is_clean():
    block = aggregate._build_v4_block(
        _synthetic_v4_matrix(l4_score=1.0), [], {"join_needed": False}
    )
    expected = (0.1 + 0.2 + 0.3 + 0.5 + 0.6) / 5
    six_level_mean = (0.1 + 0.2 + 0.3 + 1.0 + 0.5 + 0.6) / 6
    _assert_close(block["agent_score"], expected, "clean-L4 v4 mean")
    _assert(
        abs(block["agent_score"] - six_level_mean) > 1e-9,
        "clean L4 silently entered the v4 denominator",
    )


def test_adding_v4_does_not_change_v2_or_v3_headline_bytes():
    summary = _validation_summary_with_v3()
    before = json.dumps(
        {
            "v2": summary["agent_score"],
            "v3": summary["scoring_v3"]["agent_score"],
        },
        separators=(",", ":"),
    ).encode()
    with_v4 = _validation_summary_with_v4()
    after = json.dumps(
        {
            "v2": with_v4["agent_score"],
            "v3": with_v4["scoring_v3"]["agent_score"],
        },
        separators=(",", ":"),
    ).encode()
    _assert(before == after, "adding v4 changed a v2/v3 headline byte")


def test_adding_v4_does_not_change_v2_or_v3_blocks():
    v2_keys = (
        "benchmark",
        "model",
        "track",
        "scoring_version",
        "native_tool_calling",
        "agent_score",
        "scored_levels",
        "required_levels",
        "agent_score_status",
        "by_level",
    )
    before_summary = _validation_summary_with_v3()
    after_summary = _validation_summary_with_v4()
    before = json.dumps(
        {
            "v2": {key: before_summary[key] for key in v2_keys},
            "v3": before_summary["scoring_v3"],
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    after = json.dumps(
        {
            "v2": {key: after_summary[key] for key in v2_keys},
            "v3": after_summary["scoring_v3"],
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    _assert(before == after, "adding v4 changed the frozen v2/v3 blocks")


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
        "ResultFieldCoverage_det=0.500/ok(applicable=3/10)" in printed,
        "L7 result field metric or scored-task count hidden",
    )
    _assert("judge_missing" not in printed, "judge-missing metrics must stay hidden")


def test_print_table_reports_all_versions_matrix_and_l4_fixture_context():
    summary = _validation_summary_with_v4()
    summary["model"] = "x"
    summary["track"] = "agent"
    summary["cache_miss_diagnostics"] = {
        "by_level": {
            "L4": {
                "total_calls": 12,
                "cache_misses": 5,
                "miss_rate": 5 / 12,
                "counts": {},
                "miss_counts": {"query_absent": 4, "semantic_mismatch": 1},
            }
        }
    }
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        score_run.print_table(summary, 0)
    printed = output.getvalue()
    _assert(
        'version=agent_det_v2 denominator=("L1","L2","L3","L4","L5","L6")'
        in printed,
        "v2 denominator not spelled out",
    )
    _assert(
        'version=agent_det_v3 denominator=("L1","L2","L3","L4","L5","L6")'
        in printed,
        "v3 denominator not spelled out",
    )
    _assert(
        'version=agent_det_v4 denominator=("L1","L2","L3","L5","L6")'
        in printed,
        "v4 denominator not spelled out",
    )
    _assert("matrix L1" in printed and "matrix L7" in printed, "full matrix missing")
    l4_line = next(line for line in printed.splitlines() if "matrix L4" in line)
    _assert("cache_miss=5/12" in l4_line, "L4 misses are not next to its score")
    _assert("qa" in l4_line and "sm" in l4_line, "L4 bucket breakdown missing")
    _assert(
        aggregate.L4_FIXTURE_COVERAGE_NOTICE in printed,
        "L4 fixture-coverage sentence missing",
    )


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


def test_v2_only_summary_is_still_readable():
    failures, _warnings = _validate_fixture(_validation_summary())
    _assert(not failures, f"v2-only summary failed validation: {failures}")


def test_validator_accepts_v2_plus_v3_summary():
    failures, _warnings = _validate_fixture(_validation_summary_with_v3())
    _assert(not failures, f"v2+v3 summary failed validation: {failures}")


def test_validator_accepts_v2_plus_v3_plus_v4_summary():
    failures, _warnings = _validate_fixture(_validation_summary_with_v4())
    _assert(not failures, f"v2+v3+v4 summary failed validation: {failures}")


def test_validator_rejects_wrong_v4_denominator_and_mean():
    wrong_levels = _validation_summary_with_v4()
    wrong_levels["scoring_v4"]["headline_levels"] = ["L1", "L2", "L3", "L4", "L5", "L6"]
    failures, _warnings = _validate_fixture(wrong_levels)
    _assert(
        any("scoring_v4.headline_levels must be exactly" in item for item in failures),
        "wrong v4 level set passed",
    )

    wrong_mean = _validation_summary_with_v4()
    wrong_mean["scoring_v4"]["agent_score"] += 0.001
    failures, _warnings = _validate_fixture(wrong_mean)
    _assert(
        any("scoring_v4.agent_score mean invariant failed" in item for item in failures),
        "perturbed v4 mean passed",
    )


def test_validator_warns_on_single_candidate_l2_without_failing():
    with tempfile.TemporaryDirectory() as temp_dir:
        results_dir = Path(temp_dir)
        _write_validation_fixture(results_dir, _validation_summary())
        l2_path = results_dir / "L2.json"
        l2 = json.loads(l2_path.read_text(encoding="utf-8"))
        l2["results"] = [
            {"task_id": "L2-one", "exposed_tools": ["OnlyTool"]},
            {"task_id": "L2-many", "exposed_tools": ["GoldenTool", "DistractorTool"]},
        ]
        l2_path.write_text(json.dumps(l2), encoding="utf-8")
        failures, warnings = validate_run.validate_results_dir(results_dir)
    _assert(not failures, f"single-candidate warning failed validation: {failures}")
    candidate_warnings = [warning for warning in warnings if "exposed tool candidate" in warning]
    _assert(
        candidate_warnings
        == ["L2 task L2-one has only one exposed tool candidate"],
        f"single-candidate warnings mismatch: {candidate_warnings}",
    )


def test_validator_rejects_perturbed_v3_agent_score():
    summary = _validation_summary_with_v3()
    summary["scoring_v3"]["agent_score"] += 0.001
    failures, _warnings = _validate_fixture(summary)
    _assert(
        any("scoring_v3.agent_score mean invariant failed" in item for item in failures),
        "perturbed v3 mean passed",
    )


def test_validator_rejects_wrong_v3_in_score_metric_set():
    summary = _validation_summary_with_v3()
    summary["scoring_v3"]["by_level"]["L6"]["metrics"]["ToolAcc"] = {
        "score": 1.0,
        "status": "ok",
        "in_score": True,
    }
    failures, _warnings = _validate_fixture(summary)
    _assert(
        any("scoring_v3.L6 in_score metric set mismatch" in item for item in failures),
        "extra v2 metric was accepted in the v3 L6 denominator",
    )


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


def test_score_run_bootstrap_failure_exits_2_without_writes():
    with tempfile.TemporaryDirectory() as temp_dir:
        results_dir = Path(temp_dir)
        correct = _scoring_candidate()
        _write_validation_fixture(results_dir, correct)
        l6_path = results_dir / "L6.json"
        l6 = json.loads(l6_path.read_text(encoding="utf-8"))
        l6["results"][0]["golden_fields"] = []
        l6_path.write_text(json.dumps(l6), encoding="utf-8")
        summary_path = results_dir / "summary.json"
        before = summary_path.read_bytes()

        previous_base = os.environ.pop("MODEL_TEST_BASE", None)
        score_run.load_metrics_module.cache_clear()
        output = io.StringIO()
        try:
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                exit_code = score_run.main(["--results-dir", str(results_dir)])
        finally:
            if previous_base is not None:
                os.environ["MODEL_TEST_BASE"] = previous_base
            score_run.load_metrics_module.cache_clear()

        _assert(exit_code == 2, f"bootstrap failure exited {exit_code}, expected 2")
        _assert(summary_path.read_bytes() == before, "bootstrap failure replaced summary.json")
        _assert(
            not (results_dir / "summary.invalid.json").exists(),
            "bootstrap failure wrote an invalid-summary sidecar",
        )
        _assert("MODEL_TEST_BASE is required" in output.getvalue(), "bootstrap error hidden")


def test_score_run_internal_failure_preserves_existing_summary():
    with tempfile.TemporaryDirectory() as temp_dir:
        results_dir = Path(temp_dir)
        correct = _scoring_candidate()
        _write_validation_fixture(results_dir, correct)
        summary_path = results_dir / "summary.json"
        before = summary_path.read_bytes()
        original_bootstrap = score_run.load_metrics_module
        original_build = score_run.build_summary
        score_run.load_metrics_module = lambda: object()

        def fail_build(_results_dir):
            raise RuntimeError("synthetic scoring failure")

        score_run.build_summary = fail_build
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                exit_code = score_run.main(["--results-dir", str(results_dir)])
        finally:
            score_run.load_metrics_module = original_bootstrap
            score_run.build_summary = original_build

        _assert(exit_code == 2, f"internal scoring failure exited {exit_code}, expected 2")
        _assert(summary_path.read_bytes() == before, "scoring failure modified summary.json")
        _assert(
            not (results_dir / "summary.invalid.json").exists(),
            "internal scoring failure wrote a sidecar",
        )


def test_score_run_rejected_summary_writes_sidecar_only():
    with tempfile.TemporaryDirectory() as temp_dir:
        results_dir = Path(temp_dir)
        correct = _scoring_candidate()
        _write_validation_fixture(results_dir, correct)
        summary_path = results_dir / "summary.json"
        before = summary_path.read_bytes()
        rejected = _scoring_candidate()
        rejected["scoring_version"] = "rejected-version"

        exit_code, output = _run_score_candidate(results_dir, rejected)
        sidecar = results_dir / "summary.invalid.json"
        _assert(exit_code == 1, f"rejected summary exited {exit_code}, expected 1")
        _assert(summary_path.read_bytes() == before, "rejected summary replaced summary.json")
        _assert(sidecar.is_file(), "rejected summary sidecar was not written")
        _assert(json.loads(sidecar.read_text(encoding="utf-8")) == rejected, "sidecar payload mismatch")
        _assert("scoring_version mismatch" in output, "validation failure was not printed")


def test_score_run_rejects_all_legacy_metadata_without_replacing_summary():
    with tempfile.TemporaryDirectory() as temp_dir:
        results_dir = Path(temp_dir)
        candidate = _scoring_candidate()
        candidate["native_tool_calling"] = False
        native_overrides = {level: None for level in candidate["by_level"]}
        _write_validation_fixture(results_dir, candidate, native_overrides)
        summary_path = results_dir / "summary.json"
        before = summary_path.read_bytes()

        exit_code, output = _run_score_candidate(results_dir, candidate)
        sidecar = results_dir / "summary.invalid.json"
        _assert(exit_code == 1, f"legacy summary exited {exit_code}, expected 1")
        _assert(summary_path.read_bytes() == before, "legacy run replaced summary.json")
        _assert(sidecar.is_file(), "legacy run did not write an invalid-summary sidecar")
        _assert(
            json.loads(sidecar.read_text(encoding="utf-8")) == candidate,
            "legacy sidecar payload mismatch",
        )
        _assert("pre-harness-fix artifact" in output, "legacy rejection was not printed")


def test_score_run_clean_summary_uses_atomic_replace_and_clears_sidecar():
    with tempfile.TemporaryDirectory() as temp_dir:
        results_dir = Path(temp_dir)
        candidate = _scoring_candidate()
        _write_validation_fixture(results_dir, candidate)
        summary_path = results_dir / "summary.json"
        summary_path.write_text("old summary", encoding="utf-8")
        sidecar = results_dir / "summary.invalid.json"
        sidecar.write_text("stale invalid summary", encoding="utf-8")
        original_replace = score_run.os.replace
        replacements = []

        def record_replace(source, destination):
            replacements.append((Path(source), Path(destination)))
            return original_replace(source, destination)

        score_run.os.replace = record_replace
        try:
            exit_code, _output = _run_score_candidate(results_dir, candidate)
        finally:
            score_run.os.replace = original_replace

        _assert(exit_code == 0, f"clean summary exited {exit_code}, expected 0")
        _assert(json.loads(summary_path.read_text(encoding="utf-8")) == candidate, "summary payload mismatch")
        _assert(not sidecar.exists(), "clean publish left a stale invalid sidecar")
        _assert(
            any(
                source.parent.resolve() == results_dir.resolve()
                and destination.resolve() == summary_path.resolve()
                for source, destination in replacements
            ),
            "clean publish did not atomically replace summary.json",
        )


def test_score_run_full_harness_metadata_still_publishes():
    with tempfile.TemporaryDirectory() as temp_dir:
        results_dir = Path(temp_dir)
        candidate = _scoring_candidate()
        _write_validation_fixture(results_dir, candidate)
        for level in candidate["by_level"]:
            level_path = results_dir / f"{level}.json"
            raw = json.loads(level_path.read_text(encoding="utf-8"))
            raw["metadata"].update(
                {
                    "request_timeout": 60,
                    "task_timeout": 300,
                    "max_retries": 0,
                    "native_tool_calling": True,
                }
            )
            level_path.write_text(json.dumps(raw), encoding="utf-8")

        exit_code, output = _run_score_candidate(results_dir, candidate)
        published = json.loads(
            (results_dir / "summary.json").read_text(encoding="utf-8")
        )
        _assert(exit_code == 0, f"full harness metadata exited {exit_code}: {output}")
        _assert(published == candidate, "full harness metadata was not published")


def test_score_run_bad_argv_exits_2():
    with contextlib.redirect_stderr(io.StringIO()):
        exit_code = score_run.main(["--unknown-option"])
    _assert(exit_code == 2, f"bad argv exited {exit_code}, expected 2")


def test_validate_summary_agrees_with_validate_results_dir():
    with tempfile.TemporaryDirectory() as temp_dir:
        results_dir = Path(temp_dir)
        summary = _scoring_candidate()
        _write_validation_fixture(results_dir, summary)
        in_memory = validate_run.validate_summary(summary, results_dir)
        from_disk = validate_run.validate_results_dir(results_dir)
    _assert(in_memory == from_disk, f"validator split changed judgment: {in_memory!r} != {from_disk!r}")


def test_contract_error_metric_validates_and_publishes():
    with tempfile.TemporaryDirectory() as temp_dir:
        results_dir = Path(temp_dir)
        candidate = _scoring_candidate()
        metric = next(
            entry
            for entry in candidate["by_level"]["L1"]["metrics"].values()
            if entry.get("in_score") is True
        )
        metric["score"] = None
        metric["status"] = "contract_error"
        _write_validation_fixture(results_dir, candidate)
        failures, _warnings = validate_run.validate_summary(candidate, results_dir)
        _assert(not failures, f"contract_error was rejected by validator: {failures}")

        exit_code, _output = _run_score_candidate(results_dir, candidate)
        _assert(exit_code == 0, f"contract_error candidate exited {exit_code}, expected 0")
        published = json.loads((results_dir / "summary.json").read_text(encoding="utf-8"))
        _assert(published == candidate, "accepted contract_error candidate was not published")


def test_score_run_dry_run_writes_nothing_for_clean_and_rejected_summaries():
    for rejected in (False, True):
        with tempfile.TemporaryDirectory() as temp_dir:
            results_dir = Path(temp_dir)
            candidate = _scoring_candidate()
            _write_validation_fixture(results_dir, candidate)
            if rejected:
                candidate["scoring_version"] = "rejected-version"
            summary_path = results_dir / "summary.json"
            sidecar = results_dir / "summary.invalid.json"
            summary_before = summary_path.read_bytes()
            sidecar.write_bytes(b"existing sidecar")
            sidecar_before = sidecar.read_bytes()

            exit_code, _output = _run_score_candidate(
                results_dir, candidate, "--dry-run"
            )
            expected = 1 if rejected else 0
            _assert(exit_code == expected, f"dry-run rejected={rejected} exited {exit_code}")
            _assert(summary_path.read_bytes() == summary_before, "dry-run modified summary.json")
            _assert(sidecar.read_bytes() == sidecar_before, "dry-run modified the sidecar")


def test_score_run_check_matching_summary_exits_0_without_writes():
    with tempfile.TemporaryDirectory() as temp_dir:
        results_dir = Path(temp_dir)
        candidate = _scoring_candidate()
        _write_validation_fixture(results_dir, candidate)
        summary_path = results_dir / "summary.json"
        sidecar = results_dir / "summary.invalid.json"
        sidecar.write_bytes(b"existing sidecar")
        summary_before = summary_path.read_bytes()
        sidecar_before = sidecar.read_bytes()

        exit_code, output = _run_score_candidate(results_dir, candidate, "--check")

        _assert(exit_code == 0, f"matching check exited {exit_code}, expected 0")
        _assert("CHECK summary.json matches" in output, "matching result was not printed")
        _assert(summary_path.read_bytes() == summary_before, "check modified summary.json")
        _assert(sidecar.read_bytes() == sidecar_before, "check modified the sidecar")


def test_score_run_check_matching_but_invalid_exits_3_without_writes():
    with tempfile.TemporaryDirectory() as temp_dir:
        results_dir = Path(temp_dir)
        candidate = _scoring_candidate()
        candidate["scoring_version"] = "invalid-but-matching"
        _write_validation_fixture(results_dir, candidate)
        summary_path = results_dir / "summary.json"
        before = summary_path.read_bytes()

        exit_code, output = _run_score_candidate(results_dir, candidate, "--check")

        _assert(exit_code == 3, f"matching-invalid check exited {exit_code}, expected 3")
        _assert("FAIL scoring_version mismatch" in output, "validation reason was hidden")
        _assert("matches computed summary but validation failed" in output, "invalid match category missing")
        _assert("DRIFT" not in output, "matching-invalid summary was mislabeled as drift")
        _assert(summary_path.read_bytes() == before, "matching-invalid check modified summary.json")


def test_results_fresh_maps_invalid_check_and_keeps_failure_details():
    source = FRESH_RESULTS_SCRIPT.read_text(encoding="utf-8")
    _assert("elif (( rc == 3 ))" in source, "freshness wrapper does not map exit 3")
    _assert('results_log "INVALID ' in source, "freshness wrapper hides INVALID category")
    _assert(
        '*"[agent-scoring] FAIL"*' in source,
        "freshness detail filter still suppresses validation failures",
    )


def test_score_run_check_drift_exits_1_with_path_without_writes():
    with tempfile.TemporaryDirectory() as temp_dir:
        results_dir = Path(temp_dir)
        candidate = _scoring_candidate()
        stored = copy.deepcopy(candidate)
        stored["by_level"]["L1"]["score"] = 0.123456
        _write_validation_fixture(results_dir, stored)
        summary_path = results_dir / "summary.json"
        sidecar = results_dir / "summary.invalid.json"
        sidecar.write_bytes(b"existing sidecar")
        summary_before = summary_path.read_bytes()
        sidecar_before = sidecar.read_bytes()

        exit_code, output = _run_score_candidate(results_dir, candidate, "--check")

        _assert(exit_code == 1, f"drifted check exited {exit_code}, expected 1")
        _assert("DRIFT .by_level.L1.score" in output, "changed dotted path was not printed")
        _assert(summary_path.read_bytes() == summary_before, "check replaced summary.json")
        _assert(sidecar.read_bytes() == sidecar_before, "check modified the sidecar")


def test_score_run_check_missing_summary_exits_2():
    with tempfile.TemporaryDirectory() as temp_dir:
        results_dir = Path(temp_dir)
        candidate = _scoring_candidate()
        _write_validation_fixture(results_dir, candidate)
        (results_dir / "summary.json").unlink()

        exit_code, output = _run_score_candidate(results_dir, candidate, "--check")

        _assert(exit_code == 2, f"missing-summary check exited {exit_code}, expected 2")
        _assert("summary.json not found" in output, "missing summary error was not printed")
        _assert(not (results_dir / "summary.json").exists(), "check created summary.json")
        _assert(
            not (results_dir / "summary.invalid.json").exists(),
            "check created an invalid-summary sidecar",
        )


def test_score_run_check_collapses_wholly_absent_subtree():
    with tempfile.TemporaryDirectory() as temp_dir:
        results_dir = Path(temp_dir)
        stored = _scoring_candidate()
        candidate = copy.deepcopy(stored)
        candidate["fresh_block"] = {
            "branch": {f"metric_{index}": index for index in range(60)}
        }
        _write_validation_fixture(results_dir, stored)

        exit_code, output = _run_score_candidate(results_dir, candidate, "--check")

        collapsed = "DRIFT+ .fresh_block (60 leaves absent in stored)"
        _assert(exit_code == 1, f"absent-subtree check exited {exit_code}, expected 1")
        _assert(collapsed in output, "absent subtree was not collapsed with its leaf count")
        _assert(".fresh_block.branch" not in output, "absent subtree printed child differences")
        _assert(output.count("DRIFT+ .fresh_block") == 1, "absent subtree printed multiple lines")


def test_score_run_check_and_dry_run_are_mutually_exclusive():
    output = io.StringIO()
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
        exit_code = score_run.main(["--check", "--dry-run"])
    _assert(exit_code == 2, f"--check --dry-run exited {exit_code}, expected 2")
    _assert("not allowed with argument" in output.getvalue(), "mutual exclusion error hidden")


def test_validator_accepts_partial_summary():
    summary = _validation_summary()
    del summary["by_level"]["L6"]
    summary["agent_score"] = None
    summary["agent_score_status"] = "incomplete"
    summary["scored_levels"] = 5
    failures, _warnings = _validate_fixture(summary)
    _assert(not failures, f"partial summary failed validation: {failures}")


def test_validator_rejects_all_legacy_level_metadata():
    summary = _validation_summary()
    summary["native_tool_calling"] = False
    native_overrides = {level: None for level in summary["by_level"]}
    failures, warnings = _validate_fixture(summary, native_overrides)
    _assert(
        any("pre-harness-fix artifact" in failure for failure in failures),
        f"all-legacy raw levels passed validation: {failures}",
    )
    _assert(
        len([warning for warning in warnings if "treating legacy run as false" in warning])
        == len(summary["by_level"]),
        "legacy native metadata warnings mismatch",
    )


def test_validator_accepts_native_tool_calling_only_metadata():
    failures, _warnings = _validate_fixture(_validation_summary())
    _assert(
        not failures,
        f"native_tool_calling-only metadata was rejected: {failures}",
    )


def test_validator_accepts_mixed_legacy_and_current_levels_with_warning():
    with tempfile.TemporaryDirectory() as temp_dir:
        results_dir = Path(temp_dir)
        summary = _validation_summary()
        summary["native_tool_calling"] = False
        native_overrides = {level: None for level in summary["by_level"]}
        _write_validation_fixture(results_dir, summary, native_overrides)
        l1_path = results_dir / "L1.json"
        l1 = json.loads(l1_path.read_text(encoding="utf-8"))
        l1["metadata"]["native_tool_calling"] = False
        l1_path.write_text(json.dumps(l1), encoding="utf-8")

        failures, warnings = validate_run.validate_summary(summary, results_dir)

    _assert(not failures, f"mixed legacy/current levels were rejected: {failures}")
    legacy_warnings = [
        warning for warning in warnings if "treating legacy run as false" in warning
    ]
    _assert(
        len(legacy_warnings) == len(summary["by_level"]) - 1,
        f"mixed-run legacy warnings mismatch: {legacy_warnings}",
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


def test_validator_rejects_cross_level_harness_disagreement():
    values = {
        "model": ("model-a", "model-b"),
        "request_timeout": (60, 61),
        "task_timeout": (300, 301),
        "max_retries": (2, 3),
        "max_tokens": (4096, 8192),
        "sdk_max_retries": (0, 1),
        "openai_sdk_version": ("2.54.0", "2.55.0"),
    }
    for field, (common_value, mismatched_value) in values.items():
        with tempfile.TemporaryDirectory() as temp_dir:
            results_dir = Path(temp_dir)
            summary = _validation_summary()
            _write_validation_fixture(results_dir, summary)
            for level in summary["by_level"]:
                level_path = results_dir / f"{level}.json"
                raw = json.loads(level_path.read_text(encoding="utf-8"))
                raw["metadata"][field] = common_value
                if level == "L2":
                    raw["metadata"][field] = mismatched_value
                level_path.write_text(json.dumps(raw), encoding="utf-8")

            failures, _warnings = validate_run.validate_results_dir(results_dir)

        _assert(
            any(f"metadata.{field} disagrees across raw levels" in item for item in failures),
            f"cross-level {field} disagreement passed: {failures}",
        )


def test_validator_accepts_uniform_absence_of_extended_harness_fields():
    failures, _warnings = _validate_fixture(_validation_summary())
    _assert(
        not failures,
        f"uniformly absent extended harness metadata was rejected: {failures}",
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


def _write_level_report_fixture(
    results_root,
    model,
    run_name,
    timestamp,
    score,
    error_level=None,
    error_task_id=None,
):
    results_dir = results_root / model / run_name / "language" / "agent_test"
    results_dir.mkdir(parents=True)
    level_scores = (
        dict(zip(REPORT_LEVELS, score))
        if isinstance(score, (tuple, list))
        else dict.fromkeys(REPORT_LEVELS, score)
    )
    by_level = {
        level: {"score": level_scores[level], "total": 1, "applied_metrics": 1}
        for level in REPORT_LEVELS
    }
    summary = {
        "model": model,
        "scoring_v4": {"by_level": by_level},
    }
    infrastructure_by_level = {
        level: {"infrastructure_error_task_count": 0, "tasks": []}
        for level in REPORT_LEVELS
    }
    if error_level is not None:
        error_score = level_scores[error_level]
        infrastructure_by_level[error_level] = {
            "infrastructure_error_task_count": 1,
            "tasks": [
                {"task_id": error_task_id, "error_class": "TimeoutError"}
            ],
            "score_bounds": {
                "with_infrastructure_error_tasks_scored_as_zero": error_score,
                "with_infrastructure_error_tasks_excluded": min(1.0, error_score + 0.1),
            },
        }
    summary["infrastructure_error_diagnostics"] = {
        "annotation_only": True,
        "infrastructure_error_task_count": int(error_level is not None),
        "by_level": infrastructure_by_level,
    }
    (results_dir / "summary.json").write_text(
        json.dumps(summary), encoding="utf-8"
    )
    for level in REPORT_LEVELS:
        task_id = error_task_id if level == error_level else f"{level}-001"
        error = "request timed out" if level == error_level else None
        raw = {
            "metadata": {
                "timestamp": timestamp,
                "request_timeout": 300,
            },
            "results": [{"task_id": task_id, "error": error}],
        }
        (results_dir / f"{level}.json").write_text(
            json.dumps(raw), encoding="utf-8"
        )


def _run_level_report(results_root):
    completed = subprocess.run(
        [str(REPORT_SCRIPT), "--results-root", str(results_root)],
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.returncode, completed.stdout + completed.stderr


def test_level_report_prefers_clean_run_over_newer_errored_run():
    with tempfile.TemporaryDirectory() as temp_dir:
        results_root = Path(temp_dir)
        _write_level_report_fixture(
            results_root, "model-a", "clean", "2026-01-01T00:00:00", 0.111
        )
        _write_level_report_fixture(
            results_root,
            "model-a",
            "errored",
            "2026-02-01T00:00:00",
            0.999,
            error_level="L3",
            error_task_id="L3-003",
        )
        exit_code, output = _run_level_report(results_root)

    _assert(exit_code == 0, "level report failed")
    _assert("2026-01-01T00:00:00" in output, "clean run was not selected")
    _assert("0.111" in output, "clean run scores were not printed")
    _assert("0.999" not in output, "newer errored run incorrectly won selection")
    _assert("infra death" not in output, "unselected run contaminated the note")


def test_level_report_lists_model_with_only_errored_run_and_note():
    with tempfile.TemporaryDirectory() as temp_dir:
        results_root = Path(temp_dir)
        _write_level_report_fixture(
            results_root,
            "model-only-error",
            "errored",
            "2026-03-01T00:00:00",
            0.222,
            error_level="L5",
            error_task_id="L5-007",
        )
        exit_code, output = _run_level_report(results_root)

    _assert(exit_code == 0, "errored-only model made the report fail")
    _assert("model-only-error" in output, "errored-only model was omitted")
    _assert("L5 L5-007 infra death" in output, "infrastructure death note missing")
    _assert(
        "L5[as-zero=0.222,exclude=0.322]" in output,
        "affected-level contamination bounds were not surfaced",
    )


def test_level_report_has_no_composite_or_rank_field():
    # These nonuniform scores make each row's mean distinct from every level score.
    fixture_scores = {
        "model-a": (0.100, 0.200, 0.300, 0.400, 0.500, 0.600),
        "model-b": (0.200, 0.300, 0.400, 0.500, 0.600, 0.700),
    }
    with tempfile.TemporaryDirectory() as temp_dir:
        results_root = Path(temp_dir)
        for model, scores in fixture_scores.items():
            _write_level_report_fixture(
                results_root, model, "clean", "2026-01-01T00:00:00", scores
            )
        exit_code, output = _run_level_report(results_root)

    _assert(exit_code == 0, "level report failed")
    lowered = output.lower()
    for forbidden in ("agent_score", "composite", "rank"):
        _assert(forbidden not in lowered, f"forbidden report field returned: {forbidden}")
    rows_by_model = {
        line.split()[1]: line
        for line in output.splitlines()
        if len(line.split()) > 1 and line.split()[1] in fixture_scores
    }
    _assert(set(rows_by_model) == set(fixture_scores), "fixture data rows missing")
    for model, scores in fixture_scores.items():
        expected_mean = float(f"{sum(scores) / len(scores):.3f}")
        printed_numbers = [
            float(value)
            for value in re.findall(
                r"(?<![\w.])[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?(?![\w.])",
                rows_by_model[model],
            )
        ]
        _assert(
            expected_mean not in printed_numbers,
            f"unlabelled composite returned for {model}: {expected_mean:.3f}",
        )


TESTS = [
    test_level_report_prefers_clean_run_over_newer_errored_run,
    test_level_report_lists_model_with_only_errored_run_and_note,
    test_level_report_has_no_composite_or_rank_field,
    test_cache_classifier_produces_every_bucket_from_hand_built_pairs,
    test_cache_classifier_size_and_count_are_semantic,
    test_cache_classifier_presentation_fields_are_contract_pinned,
    test_cache_classifier_non_text_identity_is_semantic_not_unclassified,
    test_cache_classifier_collision_tie_break_is_deterministic,
    test_cache_diagnostic_does_not_change_v2_or_v3_headline_bytes,
    test_l3_retry_inflation_mid_miss_counts_and_ratio,
    test_l3_retry_inflation_reports_context_construction_failures,
    test_l3_retry_inflation_zero_calls_are_separate_from_one_x_baseline,
    test_l3_retry_inflation_four_classes_partition_all_tasks,
    test_l3_retry_diagnostic_is_score_and_headline_neutral,
    test_l5_ceiling_reports_observed_max_and_caps,
    test_l5_ceiling_reports_metric_producer_failure,
    test_l5_ceiling_distinguishes_all_context_failures_from_no_values,
    test_l5_ceiling_diagnostic_is_score_and_headline_neutral,
    test_possible_absorbed_request_timeout_reports_positive,
    test_possible_absorbed_request_timeout_ignores_below_timeout,
    test_possible_absorbed_request_timeout_missing_fields_are_unclassifiable,
    test_l7_partial_coverage_diagnostic_preserves_partial_entry,
    test_l7_partial_coverage_diagnostic_reports_complete_entry,
    test_new_annotation_diagnostics_are_score_and_headline_neutral,
    test_new_diagnostics_round_trip_and_validate,
    test_infrastructure_error_diagnostic_emits_both_bounds_without_rescoring,
    test_infrastructure_error_diagnostic_clean_level_has_zero_count_no_bounds,
    test_swallowed_exception_detector_fires_on_seeded_only_zero_step_task,
    test_swallowed_exception_detector_ignores_generated_zero_tool_call_l6_task,
    test_validator_warns_above_cache_threshold_without_failing,
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
    test_conversion_preserves_source_tools_and_keeps_required_tools,
    test_conversion_without_source_available_tools_keeps_legacy_exposure,
    test_simplified_artifact_records_exposed_candidate_set,
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
    test_context_prefers_persisted_exposed_tools_with_legacy_fallback,
    test_v3_task_data_prefers_persisted_fields_without_join,
    test_v3_task_data_join_rejects_missing_and_duplicate_task_ids,
    test_redundant_call_rate_empty_without_bench,
    test_redundant_call_rate_nonempty_loads_bench,
    test_refetch_avoidance_empty_one_and_missing_trace,
    test_seeded_field_recall_uses_seed_when_refetch_also_exists,
    test_seeded_field_recall_uses_seed_in_moe_artifact_or_skip,
    test_seeded_field_recall_all_and_partial,
    test_seeded_field_recall_unresolvable_is_not_applicable,
    test_seeded_field_recall_excludes_long_text_without_failure,
    test_l6_freshness_and_minimum_calls_do_not_affect_v3_metrics,
    test_context_retention_det_all_with_normalization_and_extra_args,
    test_context_retention_det_partial_and_wrong_value,
    test_context_retention_det_none_matched_and_no_data,
    test_result_field_coverage_all_and_partial,
    test_result_field_coverage_numeric_tolerance,
    test_result_field_coverage_thousands_separator,
    test_result_field_coverage_wrong_number,
    test_result_field_coverage_normalizes_string_html_and_case,
    test_result_field_coverage_excludes_long_text,
    test_result_field_coverage_unresolved_is_not_applicable,
    test_result_field_coverage_no_data_and_missing_tool_response,
    test_result_field_coverage_seed_only_applicability_denominator,
    test_result_field_coverage_diagnostics_are_aggregated,
    test_frozen_v2_l6_spec_is_unchanged,
    test_v3_l6_spec_is_exactly_two_in_score_metrics,
    test_l7_spec_is_exactly_two_record_only_metrics,
    test_seed_clone_polarity_fails_v2_and_passes_v3,
    test_judge_missing_without_call,
    test_l7_without_ground_truth_is_all_not_applicable,
    test_empty_level_spec_has_no_deterministic_metric_reason,
    test_missing_level_not_zero_filled,
    test_non_l7_none_is_unscorable,
    test_metric_error_fails_closed,
    test_metric_contract_error_fails_closed_with_diagnostics,
    test_metric_contract_accepts_unit_interval_boundaries,
    test_partial_metric_keeps_level_scorable,
    test_all_tasks_error_fails_level_closed,
    test_record_only_metric_error_does_not_fail_level,
    test_record_only_metric_contract_error_fails_level_closed,
    test_all_in_score_metrics_not_applicable,
    test_partial_run_is_incomplete,
    test_legacy_missing_native_tool_calling_defaults_false,
    test_complete_run_has_agent_score,
    test_scorable_levels_and_version_contract,
    test_v4_requires_exactly_its_five_scorable_levels,
    test_v4_l4_null_does_not_block_and_mean_is_exact,
    test_v4_exclusion_is_constant_when_l4_is_clean,
    test_adding_v4_does_not_change_v2_or_v3_headline_bytes,
    test_adding_v4_does_not_change_v2_or_v3_blocks,
    test_all_six_loaded_one_unscorable_is_incomplete,
    test_complete_six_with_l7_ignores_l7_in_headline,
    test_empty_results_are_unscorable_no_tasks,
    test_print_table_shows_partial_run_status,
    test_print_table_shows_l7_record_only_metrics_without_judges,
    test_print_table_reports_all_versions_matrix_and_l4_fixture_context,
    test_task_spread_counts_scored_tasks,
    test_applied_metrics_counts_only_scored_in_score_metrics,
    test_v2_only_summary_is_still_readable,
    test_validator_accepts_v2_plus_v3_summary,
    test_validator_accepts_v2_plus_v3_plus_v4_summary,
    test_validator_rejects_wrong_v4_denominator_and_mean,
    test_validator_warns_on_single_candidate_l2_without_failing,
    test_validator_rejects_perturbed_v3_agent_score,
    test_validator_rejects_wrong_v3_in_score_metric_set,
    test_validator_main_nonexistent_results_dir_exits_2,
    test_validator_main_missing_summary_exits_1,
    test_validator_main_complete_summary_exits_0,
    test_validator_main_unparseable_summary_exits_2,
    test_score_run_bootstrap_failure_exits_2_without_writes,
    test_score_run_internal_failure_preserves_existing_summary,
    test_score_run_rejected_summary_writes_sidecar_only,
    test_score_run_rejects_all_legacy_metadata_without_replacing_summary,
    test_score_run_clean_summary_uses_atomic_replace_and_clears_sidecar,
    test_score_run_full_harness_metadata_still_publishes,
    test_score_run_bad_argv_exits_2,
    test_validate_summary_agrees_with_validate_results_dir,
    test_contract_error_metric_validates_and_publishes,
    test_score_run_dry_run_writes_nothing_for_clean_and_rejected_summaries,
    test_score_run_check_matching_summary_exits_0_without_writes,
    test_score_run_check_matching_but_invalid_exits_3_without_writes,
    test_results_fresh_maps_invalid_check_and_keeps_failure_details,
    test_score_run_check_drift_exits_1_with_path_without_writes,
    test_score_run_check_missing_summary_exits_2,
    test_score_run_check_collapses_wholly_absent_subtree,
    test_score_run_check_and_dry_run_are_mutually_exclusive,
    test_validator_accepts_partial_summary,
    test_validator_rejects_all_legacy_level_metadata,
    test_validator_accepts_native_tool_calling_only_metadata,
    test_validator_accepts_mixed_legacy_and_current_levels_with_warning,
    test_validator_rejects_version_mismatch,
    test_validator_rejects_score_outside_unit_interval,
    test_validator_rejects_partial_in_score_metric,
    test_validator_rejects_not_applicable_numeric_score,
    test_validator_rejects_native_tool_calling_disagreement,
    test_validator_rejects_cross_level_harness_disagreement,
    test_validator_accepts_uniform_absence_of_extended_harness_fields,
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
