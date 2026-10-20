from __future__ import annotations

import json

from shared.multimodal.publish.adapters import adapt_b3, adapt_b4


def _write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def test_b3_reaggregates_raw_flags_and_rejects_summary_drift(tmp_path):
    source = tmp_path / "results/model/session/vision/customB/b3_structured_output"
    source.mkdir(parents=True)
    rows = [
        {
            "id": "a", "response": "{}", "parse_ok": True,
            "schema_check": {"required_fields_present": True, "type_match": True},
            "value_check": {"match_rate": 1.0}, "error": None,
        },
        {
            "id": "b", "response": "not json", "parse_ok": False,
            "schema_check": {"required_fields_present": False, "type_match": False},
            "value_check": {"match_rate": 0.0}, "error": None,
        },
    ]
    summary = {
        "benchmark": "B-3 Structured Output", "model": "model", "total": 2,
        "json_parse_rate": 1.0, "schema_pass_rate": 1.0, "value_match_rate": 1.0,
        "run_config": {
            "decoding": {"temperature": 0.0, "max_tokens": 10, "seed": None},
            "extra": {"manifest_size": 2, "limit": None},
        },
    }
    _write_json(source / "results.json", rows)
    _write_json(source / "summary.json", summary)

    result = adapt_b3(source)
    assert result["status"] == "REJECTED"
    assert sum("raw 재집계" in reason for reason in result["failures"]) == 3
    axes = {axis["name"]: axis for axis in result["metrics"]["axes"]}
    assert axes["json_parse"]["value"] == 0.5
    assert axes["schema_pass"]["value"] == 0.5
    assert axes["value_match"]["value"] == 0.5


def _latency_entry(ttft, total):
    return {
        "ttft": ttft, "total": total, "chunks": 4,
        "completion_tokens": None, "error": None,
    }


def _condition_summary(name):
    return {
        "condition": name, "reps": 2, "successful": 2, "failed": 0,
        "ttft": {"p50": 2.0, "p95": 2.9, "p99": 2.98, "mean": 2.0, "n": 2},
        "total": {"p50": 3.0, "p95": 3.9, "p99": 3.98, "mean": 3.0, "n": 2},
        "completion_tokens": {"p50": 4.0, "p95": 4.0, "p99": 4.0, "mean": 4.0, "n": 2},
        "tokens_per_sec": {"p50": 1.5, "p95": 1.95, "p99": 1.99, "mean": 1.5, "n": 2},
    }


def test_b4_reaggregates_runs_and_never_emits_tampered_percentile(tmp_path):
    source = tmp_path / "results/model/session/vision/customB/b4_latency_profile"
    source.mkdir(parents=True)
    names = ["text_only", "image_256px", "image_1024px"]
    runs = {name: [_latency_entry(1.0, 2.0), _latency_entry(3.0, 4.0)] for name in names}
    conditions = [_condition_summary(name) for name in names]
    conditions[0]["ttft"]["p50"] = 999.0
    summary = {
        "benchmark": "B-4 Latency Profile", "model": "model", "conditions": conditions,
        "run_config": {
            "decoding": {"temperature": 0.0, "max_tokens": 10, "seed": None},
            "extra": {"reps_per_condition": 2, "skip_multi_image": True, "prompt": "p"},
        },
    }
    _write_json(source / "runs.json", runs)
    _write_json(source / "summary.json", summary)

    result = adapt_b4(source)
    assert result["status"] == "REJECTED"
    assert any("runs.json 재집계" in reason for reason in result["failures"])
    axes = {axis["name"]: axis for axis in result["metrics"]["axes"]}
    assert axes["text_only:ttft:p50"]["value"] == 2.0
    assert all(axis["value"] != 999.0 for axis in axes.values())
