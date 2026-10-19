"""Synthetic KOFFVQA contracts checked before and after extraction."""

import json
from pathlib import Path

import pytest

from shared.multimodal.publish import adapters
from shared.multimodal.publish import adapters_koffvqa as koffvqa
from shared.multimodal.publish import adapters_common as common


@pytest.mark.parametrize("path,expected", [
    ("results/model/session/vision/koffvqa", "session"),
    ("results/model/session", "session"),
    ("results/model", None),
    ("other/model/session", None),
    ("results/model/first/results/model/second", "first"),
])
def test_session_of_uses_first_results_component(path, expected):
    assert koffvqa._session_of(Path(path)) == expected


@pytest.mark.parametrize("summary,expected", [
    ({}, "current"),
    ({"predfile": ""}, "current"),
    ({"predfile": "results/model/old/prediction.xlsx"}, "old"),
    ({"predfile": "elsewhere/prediction.xlsx"}, None),
])
def test_prediction_session_prefers_recorded_path(summary, expected):
    assert koffvqa._prediction_session(summary, Path("results/model/current/koffvqa")) == expected


def test_judge_reaggregation_preserves_failure_order_and_score_types(monkeypatch):
    monkeypatch.setitem(adapters.EXPECTED_COUNTS, "koffvqa_api_judge", 987654)
    rows = [
        {"dataset_item_id": "a", "score": 0},
        {"dataset_item_id": "a", "score": 10},
        {"score": True},
        {"dataset_item_id": "b", "score": 5.0},
        {"dataset_item_id": "c", "score": 11},
        {"dataset_item_id": "d", "error": "timeout", "score": 8},
    ]
    failures = ["existing"]
    assert koffvqa._aggregate_judge_rows(rows, {"scored": 99, "avg_score": 99}, failures) == (
        {"attempted": 6, "measured": 2, "errored": 1, "unresolved": 3, "correct_measured": 2},
        [0, 10], None, 5.0,
    )
    assert failures == [
        "existing", "judge row dataset_item_id가 누락됨", "기대 건수 987654와 다름",
        "judge 오류가 포함됨", "0~10 정수 아닌 judge 점수가 포함됨",
        "judge dataset item key가 누락되었거나 중복됨",
        "raw 재집계와 summary scored가 일치하지 않음", "raw 재집계와 summary 평균이 일치하지 않음",
    ]


def _write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def _source(tmp_path, key, *, rejudge=False):
    source = tmp_path / "results/model/current/vision/multimodal" / key
    source.mkdir(parents=True)
    config = {"decoding": {"temperature": 0, "max_tokens": 10, "seed": 7},
              "dataset": {"revision": "revision"}, "extra": {"limit": None}}
    if key == "koffvqa":
        rows = [{"prediction": "answer", "error": None}]
        summary = {"model": "model", "run_config": config}
        (source / "model_gen.xlsx").write_bytes(b"prediction")
    else:
        sibling = source.parent / "koffvqa"
        sibling.mkdir()
        prediction = sibling / "model_gen.xlsx"
        prediction.write_bytes(b"prediction")
        _write_json(sibling / "summary.json", {"run_config": config})
        rows = [{"dataset_item_id": "a", "score": 8, "error": None}]
        summary = {"target_model": "model", "judge_model": "judge", "judge_prompt_version": "v1",
                   "prediction_sha256": adapters.sha256_file(prediction), "scored": 1, "avg_score": 8,
                   "run_config": config}
        if rejudge:
            summary["predfile"] = "results/model/old/prediction.xlsx"
    _write_json(source / "results.json", rows)
    _write_json(source / "summary.json", summary)
    return source


@pytest.mark.parametrize("key,status,metrics", [
    ("koffvqa", "UNSCORED", {"axes": []}),
    ("koffvqa_api_judge", "LEGACY_REVALIDATED", {"axes": [
        {"name": "rubric", "value": 8.0, "unit": "score/10", "numerator": 8, "denominator": 1},
    ]}),
])
def test_expected_counts_setitem_reaches_registry_adapt_result(tmp_path, monkeypatch, key, status, metrics):
    source = _source(tmp_path, key)
    monkeypatch.setitem(adapters.EXPECTED_COUNTS, key, 1)
    accepted = adapters.adapt_source(source)
    assert accepted["status"] == status
    assert accepted["failures"] == []
    assert accepted["metrics"] == metrics
    assert accepted["publishable"] is (key == "koffvqa_api_judge")
    assert accepted["provisional"] is (key == "koffvqa_api_judge")
    monkeypatch.setitem(adapters.EXPECTED_COUNTS, key, 987654)
    rejected = adapters.adapt_source(source)
    assert rejected["status"] == "REJECTED"
    assert rejected["failures"] == ["기대 건수 987654와 다름"]
    assert rejected["metrics"] == metrics


@pytest.mark.parametrize("rejudge,variant", [(False, "api_judge_end_to_end"), (True, "api_judge_rejudge")])
def test_judge_session_controls_variant_and_prediction_identity(tmp_path, monkeypatch, rejudge, variant):
    source = _source(tmp_path, "koffvqa_api_judge", rejudge=rejudge)
    monkeypatch.setitem(adapters.EXPECTED_COUNTS, "koffvqa_api_judge", 1)
    result = koffvqa.adapt_koffvqa_judge(source)
    assert result["variant"] == variant
    recorded = result["protocol"]["recorded"]
    assert recorded["dataset_provenance"] == {"revision": "revision"}
    assert ("rejudged_prediction_sha256" in recorded) is rejudge
    if rejudge:
        assert recorded["rejudged_prediction_sha256"] == recorded["prediction_sha256"]
    assert [path.name for path in result["source_files"]] == ["results.json", "summary.json", "model_gen.xlsx"]


@pytest.mark.parametrize("key", ["koffvqa", "koffvqa_api_judge"])
@pytest.mark.parametrize("malformed,first_failure", [
    (False, "산출물 읽기 실패: FileNotFoundError"),
    (True, "results.json/summary.json 형식이 올바르지 않음"),
])
def test_invalid_artifacts_are_rejected(tmp_path, monkeypatch, key, malformed, first_failure):
    source = tmp_path / "results/model/session/vision/multimodal" / key
    source.mkdir(parents=True)
    if malformed:
        _write_json(source / "results.json", {})
        _write_json(source / "summary.json", [])
    monkeypatch.setitem(adapters.EXPECTED_COUNTS, key, 1)
    result = adapters.adapt_source(source)
    assert result["status"] == "REJECTED"
    expected = [first_failure, "기대 건수 1와 다름"]
    if key == "koffvqa_api_judge":
        expected += ["raw 재집계와 summary scored가 일치하지 않음", "prediction SHA 기록이 없음"]
    assert result["failures"] == expected


def test_shared_count_object_and_private_reexports():
    assert koffvqa.EXPECTED_COUNTS is adapters.EXPECTED_COUNTS is common.EXPECTED_COUNTS
    for name in ("_session_of", "_prediction_session", "_aggregate_judge_rows", "adapt_koffvqa", "adapt_koffvqa_judge"):
        assert getattr(adapters, name) is getattr(koffvqa, name)
    assert adapters.ADAPTERS["koffvqa"] is koffvqa.adapt_koffvqa
    assert adapters.ADAPTERS["koffvqa_api_judge"] is koffvqa.adapt_koffvqa_judge
