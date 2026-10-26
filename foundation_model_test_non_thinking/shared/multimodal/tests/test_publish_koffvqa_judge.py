from __future__ import annotations

import json

import pytest

from shared.multimodal.benches.koffvqa_api_judge import resolve_columns, valid_score
from shared.multimodal.publish.adapters import adapt_koffvqa_judge
from shared.multimodal.publish.schema import sha256_file


def test_koffvqa_exact_default_columns():
    columns = ["index", "question", "answer", "category", "l2-category", "prediction"]
    assert resolve_columns(columns) == ("question", "answer", "prediction")


def test_koffvqa_fuzzy_names_are_not_accepted():
    with pytest.raises(ValueError):
        resolve_columns(["my_question_text", "answer", "prediction"])


def test_koffvqa_explicit_overrides_and_duplicate_binding_guard():
    columns = ["q", "rubric", "output"]
    assert resolve_columns(columns, "q", "rubric", "output") == ("q", "rubric", "output")
    with pytest.raises(ValueError):
        resolve_columns(columns, "q", "rubric", "rubric")


@pytest.mark.parametrize("score", [0, 1, 10])
def test_integer_score_is_valid(score):
    assert valid_score(score)


@pytest.mark.parametrize("score", [True, False, -1, 11, 5.0, "5", None])
def test_non_integer_or_out_of_range_score_is_invalid(score):
    assert not valid_score(score)


def _judge_source(tmp_path, model, prediction_bytes):
    source = tmp_path / f"results/{model}/session/vision/multimodal/koffvqa_api_judge"
    generation = source.parent / "koffvqa"
    source.mkdir(parents=True)
    generation.mkdir()
    prediction = generation / f"{model}_gen.xlsx"
    prediction.write_bytes(prediction_bytes)
    rows = [
        {"idx": 0, "dataset_item_id": "item-0", "score": 8, "error": None},
        {"idx": 1, "dataset_item_id": "item-1", "score": 6, "error": None},
    ]
    summary = {
        "judge_model": "judge", "judge_prompt_version": "v1", "target_model": model,
        "prediction_sha256": sha256_file(prediction), "scored": 2, "avg_score": 7.0,
        "run_config": {
            "decoding": {"temperature": 0.0, "max_tokens": 1024, "seed": None},
            "extra": {"limit": None},
        },
    }
    (source / "results.json").write_text(json.dumps(rows), encoding="utf-8")
    (source / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    (generation / "summary.json").write_text(json.dumps({
        "run_config": {"dataset": {"revision": "same-dataset-revision"}},
    }), encoding="utf-8")
    return source


def test_prediction_sha_binds_artifact_but_does_not_split_judge_cohort(monkeypatch, tmp_path):
    from shared.multimodal.publish import adapters

    monkeypatch.setitem(adapters.EXPECTED_COUNTS, "koffvqa_api_judge", 2)
    first = adapt_koffvqa_judge(_judge_source(tmp_path, "model-a", b"prediction-a"))
    second = adapt_koffvqa_judge(_judge_source(tmp_path, "model-b", b"prediction-b"))
    assert first["protocol"]["recorded"]["prediction_sha256"] != second["protocol"]["recorded"]["prediction_sha256"]
    assert first["protocol"]["recorded"]["dataset_item_digest"] == second["protocol"]["recorded"]["dataset_item_digest"]
    assert first["protocol"]["fingerprint"] == second["protocol"]["fingerprint"]
    # Explicit omission is known protocol, unlike a legacy unknown temperature.
    source = tmp_path / "results/model-b/session/vision/multimodal/koffvqa_api_judge"
    saved = json.loads((source / "summary.json").read_text())
    saved["run_config"]["decoding"]["temperature"] = None
    (source / "summary.json").write_text(json.dumps(saved))
    unknown = adapt_koffvqa_judge(source)
    assert "temperature" in unknown["protocol"]["unknown"]
    saved["judge_request"] = {"temperature": None, "temperature_mode": "omit", "reasoning_effort": "none"}
    saved["run_config"]["decoding"]["temperature_mode"] = "omit"
    (source / "summary.json").write_text(json.dumps(saved))
    omitted = adapt_koffvqa_judge(source)
    assert "temperature" not in omitted["protocol"]["unknown"]
    assert omitted["protocol"]["recorded"]["temperature"] is None
    assert omitted["protocol"]["recorded"]["judge_temperature_mode"] == "omit"
    assert omitted["protocol"]["recorded"]["judge_reasoning_effort"] == "none"
    assert len({row["protocol"]["fingerprint"] for row in (first, unknown, omitted)}) == 3
    # Rejudge remains a distinct diagnostic variant with the prediction SHA in its identity.
    import shutil
    dest = tmp_path / "results/model-b/rejudge/vision/multimodal/koffvqa_api_judge"
    shutil.copytree(source, dest)
    saved["predfile"] = str(source.parent / "koffvqa/model-b_gen.xlsx")
    (dest / "summary.json").write_text(json.dumps(saved))
    rejudged = adapt_koffvqa_judge(dest)
    assert rejudged["variant"] == "api_judge_rejudge"
    assert rejudged["protocol"]["recorded"]["rejudged_prediction_sha256"] == saved["prediction_sha256"]
    assert rejudged["protocol"]["fingerprint"] != omitted["protocol"]["fingerprint"]
