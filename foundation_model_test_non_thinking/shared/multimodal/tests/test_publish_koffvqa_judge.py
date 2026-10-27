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

    # C3: exercise derive, report tables, representative selection and strict policy.
    import copy
    from shared.multimodal.publish.derive import derive_source
    from shared.multimodal.publish.report import render_markdown, strict_failed, reproducibility_checks
    from shared.multimodal.publish.select import select_representatives
    migration_runs = []
    for model in ("model-a", "model-b"):
        original = tmp_path / f"results/{model}/session/vision/multimodal/koffvqa_api_judge"
        current = json.loads((original / "summary.json").read_text())
        current.update(rejudge_purpose="migration", judge_prompt_template_sha256="sha256:" + "a" * 64,
                       predfile=str(original.parent / f"koffvqa/{model}_gen.xlsx"))
        current["run_config"]["decoding"] = {"temperature": 0.0, "max_tokens": 1024, "seed": 0}
        current.pop("judge_request", None)
        for rep in (1, 2, 3):
            generation = tmp_path / f"results/{model}/generation{rep}/vision/multimodal/koffvqa"
            generation.mkdir(parents=True)
            prediction = generation / f"{model}_gen.xlsx"
            prediction.write_bytes(f"{model}-generation-{rep}".encode())
            current["predfile"] = str(prediction)
            current["prediction_sha256"] = sha256_file(prediction)
            current["run_config"]["timestamp_utc"] = f"2026-01-0{rep}T00:00:00+00:00"
            migrated_dir = tmp_path / f"results/{model}/migration{rep}/vision/multimodal/koffvqa_api_judge"
            shutil.copytree(original, migrated_dir)
            (migrated_dir / "summary.json").write_text(json.dumps(current))
            migration_runs.append(derive_source(migrated_dir, tmp_path)[1])
        # Explicit purpose alone cannot certify same/unknown source sessions.
        for invalid_pred in (str(original.parent / f"koffvqa/{model}_gen.xlsx"), "unidentified.xlsx"):
            bad = {**current, "predfile": invalid_pred}
            (original / "summary.json").write_text(json.dumps(bad))
            rejected = adapt_koffvqa_judge(original)
            assert rejected["status"] == "REJECTED" and not rejected["publishable"]
            assert "migration은 식별 가능한 교차 세션 재판정이어야 함" in rejected["failures"]
        for purpose in ("unexpected", None):
            (migrated_dir / "summary.json").write_text(json.dumps({**current, "rejudge_purpose": purpose}))
            assert not adapt_koffvqa_judge(migrated_dir)["publishable"]
        missing_hash = dict(current)
        missing_hash.pop("judge_prompt_template_sha256")
        (migrated_dir / "summary.json").write_text(json.dumps(missing_hash))
        assert "migration 판정 프롬프트 템플릿 SHA 기록이 없음" in adapt_koffvqa_judge(migrated_dir)["failures"]
        (migrated_dir / "summary.json").write_text(json.dumps(current))
    assert len({run["protocol"]["fingerprint"] for run in migration_runs}) == 1
    assert all(run["publishable"] and run["status"] == "LEGACY_REVALIDATED" and not run["failures"] for run in migration_runs)
    selected, ambiguous = select_representatives(migration_runs)
    assert len(selected) == 2 and not ambiguous
    assert all(check["tolerance"] == 0.10 and check["passed"] for check in reproducibility_checks(selected))
    assert not strict_failed(migration_runs, [], ambiguous)
    # Distinct legacy variants remain separate report tables even with identical scores.
    legacy = []
    for variant in ("api_judge_end_to_end", "api_judge_rejudge"):
        run = copy.deepcopy(migration_runs[0])
        run["variant"] = variant
        legacy.append(run)
    markdown, _ = render_markdown(migration_runs + legacy, [])
    headings = [line for line in markdown.splitlines() if line.startswith("### KOFFVQA-judge")]
    assert len(headings) == 3 and sum("api_judge_migration" in line for line in headings) == 1
    migration_table = markdown.split(next(line for line in headings if "api_judge_migration" in line))[1].split("### ")[0]
    assert "model-a" in migration_table and "model-b" in migration_table
    assert "판정기 교체용 재판정(생성 고정 아님)" in markdown
    # Fixed-prediction reruns are not independent generation repeats, even if newer.
    duplicate = copy.deepcopy(migration_runs[0])
    duplicate.update(session="rerun", completed_at_utc="2026-02-01T00:00:00+00:00")
    runs = migration_runs + [duplicate]
    selected, ambiguous = select_representatives(runs)
    assert len(selected) == 1 and selected[0]["model"] == "model-b"
    assert len(ambiguous) == 1 and "prediction SHA 누락 또는 중복" in ambiguous[0]["reason"]
    assert strict_failed(runs, [], ambiguous)
    # Existing exact-copy folding still works for the same session and artifacts.
    selected, ambiguous = select_representatives(migration_runs + [copy.deepcopy(migration_runs[0])])
    assert len(selected) == 2 and not ambiguous
    changed = copy.deepcopy(migration_runs)
    changed[0]["metrics"]["axes"][0].update(value=8.0, numerator=16)
    assert strict_failed(changed, [], [])
