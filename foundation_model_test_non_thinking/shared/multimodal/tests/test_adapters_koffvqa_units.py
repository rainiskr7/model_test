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
    assert result["publishable"] is True and result["failures"] == []
    if rejudge:
        from derive_multimodal_publish import main as derive_main
        from shared.multimodal.publish import report
        from shared.multimodal.publish.schema import sidecar_path

        sibling = source.parent / "koffvqa"
        original = source.parents[3] / "old/vision/multimodal/koffvqa"
        original.parent.mkdir(parents=True)
        sibling.rename(original)
        prediction = original / "model_gen.xlsx"
        summary = json.loads((source / "summary.json").read_text())
        # The recorded absolute base is obsolete; only the session is reused.
        summary["predfile"] = "/retired/base/results/model/old/vision/multimodal/koffvqa/model_gen.xlsx"
        _write_json(source / "summary.json", summary)
        relocated = koffvqa.adapt_koffvqa_judge(source)
        assert relocated["status"] == "LEGACY_REVALIDATED"
        assert relocated["publishable"] is True and relocated["failures"] == []
        assert relocated["variant"] == "api_judge_rejudge"
        assert relocated["protocol"] == result["protocol"]
        assert relocated["protocol"]["recorded"]["rejudged_prediction_sha256"] == adapters.sha256_file(prediction)
        assert relocated["source_files"] == [source / "results.json", source / "summary.json", prediction]
        before = {p: p.read_bytes() for p in (source / "results.json", source / "summary.json",
                                              prediction, original / "summary.json")}
        assert derive_main(["--base", str(tmp_path), "--source", str(source), "--write"]) == 0
        sidecar = json.loads(sidecar_path(source).read_text())
        assert sidecar["status"] == "LEGACY_REVALIDATED"
        assert sidecar["publishable"] is True and sidecar["failures"] == []
        assert prediction.relative_to(tmp_path).as_posix() in [a["path"] for a in sidecar["source"]["artifacts"]]
        loaded, missing = report.collect(tmp_path, run="current")
        assert len(loaded) == 1 and missing == [] and loaded[0]["publishable"] is True
        assert all(p.read_bytes() == value for p, value in before.items())

        prediction.write_bytes(b"changed prediction")
        rejected = koffvqa.adapt_koffvqa_judge(source)
        assert rejected["publishable"] is False
        assert rejected["failures"] == ["prediction SHA가 생성 산출물과 일치하지 않음"]
        loaded, missing = report.collect(tmp_path, run="current")
        assert loaded == [] and len(missing) == 1
        assert "sha256 mismatch" in missing[0]["reason"]
        prediction.write_bytes(before[prediction])
        original.rename(tmp_path / "saved-generation")
        rejected = koffvqa.adapt_koffvqa_judge(source)
        assert rejected["publishable"] is False
        assert rejected["failures"] == ["prediction SHA가 생성 산출물과 일치하지 않음"]
        (tmp_path / "saved-generation").rename(original)

        # A present but wrong sibling must not silently fall back to the original.
        sibling.mkdir()
        (sibling / "wrong_gen.xlsx").write_bytes(b"wrong")
        assert koffvqa.adapt_koffvqa_judge(source)["failures"] == ["prediction SHA가 생성 산출물과 일치하지 않음"]
        (sibling / "wrong_gen.xlsx").unlink()
        sibling.rmdir()
        for predfile in (None, "elsewhere/prediction.xlsx"):
            _write_json(source / "summary.json", {**summary, "predfile": predfile})
            rejected = koffvqa.adapt_koffvqa_judge(source)
            assert rejected["variant"] == "api_judge_end_to_end"
            assert rejected["publishable"] is False
        _write_json(source / "summary.json", summary)

        second = source.parents[3] / "second/vision/multimodal/koffvqa_api_judge"
        second.mkdir(parents=True)
        other = source.parents[3] / "old2/vision/multimodal/koffvqa"
        other.mkdir(parents=True)
        (other / "model_gen.xlsx").write_bytes(b"other predictions")
        (other / "summary.json").write_bytes((original / "summary.json").read_bytes())
        (second / "results.json").write_bytes((source / "results.json").read_bytes())
        _write_json(second / "summary.json", {**summary,
                    "predfile": str(other / "model_gen.xlsx"),
                    "prediction_sha256": adapters.sha256_file(other / "model_gen.xlsx")})
        different = koffvqa.adapt_koffvqa_judge(second)
        assert different["publishable"] is True and different["failures"] == []
        assert different["variant"] == "api_judge_rejudge"
        assert different["protocol"]["recorded"]["judge_model"] == recorded["judge_model"]
        assert different["protocol"]["fingerprint"] != relocated["protocol"]["fingerprint"]


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
