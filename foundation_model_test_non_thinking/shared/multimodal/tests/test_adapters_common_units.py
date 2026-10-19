"""9-2a common-helper contracts captured before moving the original functions."""

import json
from pathlib import Path

import pytest

from shared.multimodal.publish import adapters, adapters_accuracy, adapters_common as common, schema
from shared.multimodal.publish.schema import PublishStatus, RecordClass


def test_load_json_preserves_values_and_key_order(tmp_path):
    path = tmp_path / "input.json"
    path.write_text('{"한글": [1, null], "last": false}', encoding="utf-8")
    result = common.load_json(path)
    assert result == {"한글": [1, None], "last": False}
    assert list(result) == ["한글", "last"]


def test_load_json_propagates_parse_failure(tmp_path):
    path = tmp_path / "bad.json"
    path.write_bytes(b"{")
    with pytest.raises(json.JSONDecodeError):
        common.load_json(path)


@pytest.mark.parametrize("num,den,unit,expected", [
    (1, 2, "fraction", {"numerator": 1, "denominator": 2, "value": 0.5, "unit": "fraction"}),
    (0, 0, "score", {"numerator": 0, "denominator": 0, "value": None, "unit": "score"}),
])
def test_fraction(num, den, unit, expected):
    result = common._fraction(num, den, unit)
    assert result == expected
    assert list(result) == ["numerator", "denominator", "value", "unit"]


def test_counts_keep_record_identity_order_and_response_field():
    rows = [{"prediction": ""}, {"prediction": {"error": "failed"}}, {"prediction": None}]
    counts, classified = common._counts(iter(rows), "prediction")
    assert counts == {"attempted": 3, "measured": 1, "errored": 1, "unresolved": 1}
    assert [kind for _, kind in classified] == [RecordClass.MEASURED, RecordClass.ERRORED, RecordClass.UNRESOLVED]
    assert all(row is original for (row, _), original in zip(classified, rows))


def test_run_config_embedded_dict_wins_without_copy(tmp_path):
    (tmp_path / "run_config.json").write_bytes(b"invalid JSON")
    config = {"model": {"name": "model"}}
    assert common._run_config({"run_config": config}, tmp_path) is config


def test_run_config_disk_and_non_object_fallback(tmp_path):
    assert common._run_config({}, tmp_path) == {}
    path = tmp_path / "run_config.json"
    path.write_text('{"source": "disk"}', encoding="utf-8")
    assert common._run_config({"run_config": []}, tmp_path) == {"source": "disk"}
    path.write_text("[]", encoding="utf-8")
    assert common._run_config({}, tmp_path) == {}


@pytest.mark.parametrize("unknown,failures,forced,status,expected_failures,expected_warnings", [
    (["seed"], [], None, PublishStatus.LEGACY_REVALIDATED, [], ["비교 비핵심 provenance 미기록: seed"]),
    (["split", "limit"], [], None, PublishStatus.INSUFFICIENT_PROVENANCE,
     ["비교에 필요한 provenance가 복원되지 않음: limit, split"], []),
    (["split"], ["rejected"], PublishStatus.NATIVE, PublishStatus.REJECTED, ["rejected"], []),
])
def test_base_result_status_precedence_and_complete_payload(unknown, failures, forced, status,
                                                          expected_failures, expected_warnings):
    warnings = []
    result = common._base_result(
        benchmark_key="k_dtcbench", variant="full", model="model", source_dir=Path("source"),
        source_files=[Path("source/results.json")], counts={"attempted": 1}, metrics={"axes": []},
        protocol={"unknown": unknown}, completed_at_utc=None, failures=failures,
        warnings=warnings, forced_status=forced,
    )
    assert result == {
        "benchmark_id": "K-DTCBench", "benchmark_key": "k_dtcbench", "variant": "full",
        "model": "model", "source_dir": Path("source"), "source_files": [Path("source/results.json")],
        "status": status, "publishable": status is PublishStatus.LEGACY_REVALIDATED,
        "provisional": False, "aggregation_allowed": False, "completed_at_utc": None,
        "counts": {"attempted": 1}, "metrics": {"axes": []}, "protocol": {"unknown": unknown},
        "failures": expected_failures, "warnings": expected_warnings,
    }
    assert warnings == expected_warnings
    assert result["warnings"] is warnings
    assert list(result) == [
        "benchmark_id", "benchmark_key", "variant", "model", "source_dir", "source_files",
        "status", "publishable", "provisional", "aggregation_allowed", "completed_at_utc",
        "counts", "metrics", "protocol", "failures", "warnings",
    ]


@pytest.mark.parametrize("stored,calculated,expected", [
    (None, None, True), (None, 0, False), (True, 1, False), (False, False, True),
    (1.0, 1.0 + 1e-13, True), (1.0, 1.001, False), ("1", 1, False),
])
def test_same_metric_handles_null_bool_numeric_tolerance(stored, calculated, expected):
    assert common._same_metric(stored, calculated) is expected


def test_shared_constants_are_identical_objects_not_copies():
    for name in ("EXPECTED_COUNTS", "BENCHMARK_IDS", "BENCHMARK_KEYS"):
        assert getattr(adapters, name) is getattr(common, name) is getattr(adapters_accuracy, name)
    assert adapters.COMPARISON_CRITICAL_UNKNOWN is common.COMPARISON_CRITICAL_UNKNOWN is schema.COMPARISON_CRITICAL_UNKNOWN
    assert adapters.KRETA_ANSWER_PARSER_SPEC is adapters_accuracy.KRETA_ANSWER_PARSER_SPEC is schema.KRETA_ANSWER_PARSER_SPEC


@pytest.mark.parametrize("module,names", [
    (common, "load_json _fraction _counts _run_config _base_result _same_metric"),
    (adapters_accuracy, "_score_classified_records summarize_records parse_kreta_response _choice "
     "_normalize_answer _mtvqa_match _accuracy_item_keys _accuracy_protocol adapt_accuracy "
     "_kreta_mode _kreta_axes _read_kreta_rows _kreta_upstream_accuracy adapt_kreta"),
])
def test_moved_private_and_public_functions_are_reexported_identically(module, names):
    for name in names.split():
        assert getattr(adapters, name) is getattr(module, name)


def test_all_original_module_names_remain_available():
    assert set(ORIGINAL_NAMES) <= vars(adapters).keys()


# Module names captured before extraction, including private and imported names.
ORIGINAL_NAMES = ['ADAPTERS',
 'Any',
 'BENCHMARK_IDS',
 'BENCHMARK_KEYS',
 'COMPARISON_CRITICAL_UNKNOWN',
 'Callable',
 'EXPECTED_COUNTS',
 'Iterable',
 'KRETA_ANSWER_PARSER_HASH',
 'KRETA_ANSWER_PARSER_SPEC',
 'KRETA_ANSWER_PARSER_VERSION',
 'Mapping',
 'Path',
 'PublishStatus',
 'RecordClass',
 '_accuracy_item_keys',
 '_accuracy_protocol',
 '_add_dataset_provenance',
 '_add_decoding',
 '_aggregate_judge_rows',
 '_aggregate_latency_conditions',
 '_b3_raw_metrics',
 '_b4_raw_summary',
 '_b4_summary_matches',
 '_base_result',
 '_choice',
 '_counts',
 '_dataset_revision',
 '_fraction',
 '_judge_protocol',
 '_kreta_axes',
 '_kreta_mode',
 '_kreta_protocol',
 '_kreta_upstream_accuracy',
 '_mtvqa_match',
 '_normalize_answer',
 '_percentiles',
 '_prediction_session',
 '_read_kreta_rows',
 '_run_config',
 '_same_metric',
 '_score_classified_records',
 '_session_of',
 'adapt_accuracy',
 'adapt_b3',
 'adapt_b4',
 'adapt_koffvqa',
 'adapt_koffvqa_judge',
 'adapt_kreta',
 'adapt_source',
 'annotations',
 'classify_record',
 'dataset_item_digest',
 'defaultdict',
 'json',
 'load_json',
 'make_protocol',
 'math',
 'parse_kreta_response',
 're',
 'sha256_file',
 'summarize_records',
 'unicodedata']
