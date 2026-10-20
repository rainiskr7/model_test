"""Literal customB reaggregation contracts, using only synthetic artifacts."""

from copy import deepcopy
import json

import pytest

from shared.multimodal.publish import adapters
from shared.multimodal.publish import adapters_customb as customb
from shared.multimodal.publish import adapters_common as common


@pytest.mark.parametrize("rows,expected", [
    ([], {"json_parse_rate": 0.0, "schema_pass_rate": 0.0, "value_match_rate": None,
          "json_parse_numerator": 0, "schema_pass_numerator": 0, "value_count": 0}),
    ([{"parse_ok": True, "schema_check": {"required_fields_present": True, "type_match": True},
       "value_check": {"match_rate": 0.25}},
      {"parse_ok": 1, "schema_check": {"required_fields_present": 1, "type_match": True},
       "value_check": {"match_rate": True}},
      {"schema_check": "invalid", "value_check": {"match_rate": "1"}},
      {"value_check": {"match_rate": 0.75}}],
     {"json_parse_rate": 0.25, "schema_pass_rate": 0.25, "value_match_rate": 0.5,
      "json_parse_numerator": 1, "schema_pass_numerator": 1, "value_count": 2}),
])
def test_b3_raw_metrics_checks_literal_booleans_and_numeric_values(rows, expected):
    assert customb._b3_raw_metrics(rows) == expected


@pytest.mark.parametrize("values,expected", [
    ([None, True, False, "3"], {"p50": None, "p95": None, "p99": None, "mean": None, "n": 0}),
    ([7, False], {"p50": 7.0, "p95": 7.0, "p99": 7.0, "mean": 7.0, "n": 1}),
    ([3, None, 1, "2", True], {"p50": 2.0, "p95": 2.8999999999999995, "p99": 2.9799999999999995, "mean": 2.0, "n": 2}),
])
def test_percentiles_filter_and_interpolate(values, expected):
    assert customb._percentiles(iter(values)) == expected


# Literal summaries captured against the original implementation, not computed
# by the function under test to construct its own expected result.
RAW_SUMMARY = {
    "condition": "text_only", "reps": 2, "successful": 2, "failed": 0,
    "ttft": {"p50": 2.0, "p95": 2.8999999999999995, "p99": 2.9799999999999995, "mean": 2.0, "n": 2},
    "total": {"p50": 3.0, "p95": 3.9, "p99": 3.98, "mean": 3.0, "n": 2},
    "completion_tokens": {"p50": 4.0, "p95": 4.0, "p99": 4.0, "mean": 4.0, "n": 2},
    "tokens_per_sec": {"p50": 1.5, "p95": 1.95, "p99": 1.99, "mean": 1.5, "n": 2},
}
ROWS = [{"ttft": 1, "total": 2, "completion_tokens": 0, "chunks": 4},
        {"ttft": 3, "total": 4, "completion_tokens": None, "chunks": 4}]


def test_b4_raw_summary_uses_chunks_for_zero_and_null_tokens():
    assert customb._b4_raw_summary("text_only", ROWS) == RAW_SUMMARY


def test_b4_raw_summary_error_and_boolean_timing_contract():
    assert customb._b4_raw_summary("x", [
        {"ttft": False, "total": True, "completion_tokens": True, "error": "timeout"},
        {"ttft": None, "total": 0, "chunks": 4},
    ]) == {
        "condition": "x", "reps": 2, "successful": 1, "failed": 1,
        "ttft": {"p50": None, "p95": None, "p99": None, "mean": None, "n": 0},
        "total": {"p50": 0.0, "p95": 0.0, "p99": 0.0, "mean": 0.0, "n": 1},
        "completion_tokens": {"p50": 4.0, "p95": 4.0, "p99": 4.0, "mean": 4.0, "n": 1},
        "tokens_per_sec": {"p50": 1.0, "p95": 1.0, "p99": 1.0, "mean": 1.0, "n": 1},
    }


@pytest.mark.parametrize("change,expected", [
    (None, True), ("condition", False), ("metric_shape", False),
    ("percentile", False), ("bool_count", False), ("tolerance", True),
])
def test_b4_summary_matches_validates_structure_and_metric_types(change, expected):
    stored = deepcopy(RAW_SUMMARY)
    if change == "condition":
        stored["condition"] = "other"
    elif change == "metric_shape":
        stored["ttft"] = []
    elif change == "percentile":
        stored["ttft"]["p95"] = 999
    elif change == "bool_count":
        stored["ttft"]["n"] = True
    elif change == "tolerance":
        stored["ttft"]["p95"] += 1e-13
    assert customb._b4_summary_matches(stored, RAW_SUMMARY) is expected


def test_aggregate_latency_valid_and_incomplete_conditions():
    failures = []
    assert customb._aggregate_latency_conditions(
        {"text_only": ROWS}, {"conditions": [RAW_SUMMARY]}, {"text_only"}, 2, failures=failures,
    ) == ({"attempted": 2, "measured": 2, "errored": 0, "unresolved": 0, "correct_measured": 2},
          {"text_only": RAW_SUMMARY})
    assert failures == []
    failures = ["existing"]
    assert customb._aggregate_latency_conditions(
        {"other": []}, {}, {"text_only"}, 2, failures=failures,
    ) == ({"attempted": 0, "measured": 0, "errored": 0, "unresolved": 0, "correct_measured": 0}, {})
    assert failures == ["existing", "condition/rep 완주 조건을 충족하지 않음",
                        "condition 집합이 run_config와 일치하지 않음", "summary condition 집합이 일치하지 않음"]


def _source(tmp_path, key, *, drift=False):
    source = tmp_path / "results/model/session/vision/customB" / key
    source.mkdir(parents=True)
    config = {"decoding": {"temperature": 0, "max_tokens": 10, "seed": 7}}
    if key == "b3_structured_output":
        raw_name = "results.json"
        raw = [{"response": "{}", "parse_ok": True,
                "schema_check": {"required_fields_present": True, "type_match": True},
                "value_check": {"match_rate": 0.5}}]
        config["extra"] = {"manifest_size": 1, "limit": None}
        summary = {"model": "model", "json_parse_rate": 0 if drift else 1,
                   "schema_pass_rate": 1, "value_match_rate": 0.5, "run_config": config}
    else:
        raw_name = "runs.json"
        names = ["text_only", "image_256px", "image_1024px"]
        raw = {name: ROWS for name in names}
        conditions = [dict(deepcopy(RAW_SUMMARY), condition=name) for name in names]
        if drift:
            conditions[0]["ttft"]["p50"] = 999
        config["extra"] = {"reps_per_condition": 2, "skip_multi_image": True, "prompt": "p"}
        summary = {"model": "model", "conditions": conditions, "run_config": config}
    (source / raw_name).write_text(json.dumps(raw), encoding="utf-8")
    (source / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    return source


@pytest.mark.parametrize("drift", [False, True])
def test_adapt_b3_uses_raw_metrics_and_rejects_drift(tmp_path, drift):
    result = customb.adapt_b3(_source(tmp_path, "b3_structured_output", drift=drift))
    assert result["status"] == ("REJECTED" if drift else "LEGACY_REVALIDATED")
    assert result["failures"] == (["raw 재집계와 summary json_parse_rate가 일치하지 않음"] if drift else [])
    assert result["counts"] == {"attempted": 1, "measured": 1, "errored": 0, "unresolved": 0, "correct_measured": 1}
    assert result["metrics"] == {"axes": [
        {"name": "json_parse", "numerator": 1, "denominator": 1, "value": 1.0, "unit": "fraction"},
        {"name": "schema_pass", "numerator": 1, "denominator": 1, "value": 1.0, "unit": "fraction"},
        {"name": "value_match", "numerator": None, "denominator": 1, "value": 0.5, "unit": "fraction"},
    ]}


@pytest.mark.parametrize("drift", [False, True])
def test_adapt_b4_uses_raw_percentiles_and_ordered_axes(tmp_path, drift):
    result = customb.adapt_b4(_source(tmp_path, "b4_latency_profile", drift=drift))
    assert result["status"] == ("REJECTED" if drift else "LEGACY_REVALIDATED")
    assert result["failures"] == (["runs.json 재집계와 summary condition 수치가 일치하지 않음"] if drift else [])
    assert result["counts"] == {"attempted": 6, "measured": 6, "errored": 0, "unresolved": 0, "correct_measured": 6}
    axes = result["metrics"]["axes"]
    assert len(axes) == 27
    assert axes[:3] == [
        {"name": "image_1024px:ttft:p50", "value": 2.0, "unit": "seconds"},
        {"name": "image_1024px:ttft:p95", "value": 2.8999999999999995, "unit": "seconds"},
        {"name": "image_1024px:ttft:p99", "value": 2.9799999999999995, "unit": "seconds"},
    ]
    assert axes[-3:] == [
        {"name": "text_only:tokens_per_sec:p50", "value": 1.5, "unit": "tokens/second"},
        {"name": "text_only:tokens_per_sec:p95", "value": 1.95, "unit": "tokens/second"},
        {"name": "text_only:tokens_per_sec:p99", "value": 1.99, "unit": "tokens/second"},
    ]


@pytest.mark.parametrize("key", ["b3_structured_output", "b4_latency_profile"])
def test_registry_setitem_reaches_dispatch(tmp_path, monkeypatch, key):
    source = _source(tmp_path, key)
    sentinel = {"sentinel": key}
    calls = []

    def replacement(path):
        calls.append(path)
        return sentinel

    monkeypatch.setitem(adapters.ADAPTERS, key, replacement)
    assert adapters.adapt_source(source) is sentinel
    assert calls == [source]


def test_private_reexports_and_common_functions_are_identical():
    for name in ("_b3_raw_metrics", "adapt_b3", "_percentiles", "_b4_raw_summary", "_b4_summary_matches",
                 "_aggregate_latency_conditions", "adapt_b4"):
        assert getattr(adapters, name) is getattr(customb, name)
    for name in ("load_json", "_counts", "_run_config", "_base_result", "_same_metric", "_fraction"):
        assert getattr(customb, name) is getattr(common, name)
    assert adapters.ADAPTERS["b3_structured_output"] is customb.adapt_b3
    assert adapters.ADAPTERS["b4_latency_profile"] is customb.adapt_b4
