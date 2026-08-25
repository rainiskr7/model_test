from __future__ import annotations

from shared.multimodal.publish.report import render_markdown, strict_failed
from shared.multimodal.publish.schema import make_protocol
from shared.multimodal.publish.select import select_representatives


def sidecar(
    session,
    timestamp,
    *,
    status="LEGACY_REVALIDATED",
    score=1,
    source=None,
    benchmark="bench",
    variant="full",
    model="model",
    item_digest="digest-a",
    dataset_commit=None,
    axes=None,
    no_answer=None,
    parser_disagreement=None,
    artifact_sha=None,
    canonical_model=None,
    identity_mapped=True,
    artifacts=None,
    provisional=False,
):
    publishable = status in {"LEGACY_REVALIDATED", "NATIVE"}
    source_unit = source or f"results/model/{session}/bench"
    value = {
        "schema_version": 1,
        "benchmark_id": benchmark,
        "benchmark_key": benchmark,
        "variant": variant,
        "model": model,
        "session": session,
        "source": {
            "unit": source_unit,
            "artifacts": (
                artifacts if artifacts is not None else
                [{"path": f"{source_unit}/results.json", "sha256": artifact_sha}]
                if artifact_sha else []
            ),
        },
        "status": status,
        "publishable": publishable,
        "provisional": provisional,
        "aggregation_allowed": False,
        "completed_at_utc": timestamp,
        "counts": {"attempted": 1, "measured": 1, "errored": 0, "unresolved": 0, "correct_measured": score},
        "metrics": {"axes": axes or [{"name": "overall", "numerator": score, "denominator": 1, "value": score, "unit": "fraction"}]},
        "protocol": make_protocol(
            {
                "dataset_item_digest": item_digest,
                "dataset_provenance": {"git_commit": dataset_commit},
            },
            {},
            [],
        ),
        "failures": [] if publishable else ["blocked"],
        "warnings": [],
    }
    if canonical_model is not None:
        value["model_identity"] = {
            "canonical_id": canonical_model,
            "serving_name": model,
            "mapped": identity_mapped,
        }
    if no_answer is not None:
        value["no_answer_rate"] = {
            "numerator": no_answer, "denominator": 100,
            "value": no_answer / 100, "unit": "fraction",
        }
    if parser_disagreement is not None:
        value["upstream_comparison"] = {
            "upstream_accuracy": 80.0,
            "parser_disagreement_rows": parser_disagreement,
            "disagreement_ours_empty": parser_disagreement - 2,
            "disagreement_different_choice": 2,
            "note": "상류 파생 필드는 채점 근거로 쓰지 않음",
        }
    return value


def test_latest_timestamp_wins_without_score_or_run_name_tiebreak():
    older_high = sidecar("zzz-high-score", "2026-01-01T00:00:00+00:00", score=1)
    newer_low = sidecar("aaa-low-score", "2026-01-02T00:00:00+00:00", score=0)
    selected, ambiguous = select_representatives([older_high, newer_low])
    assert len(selected) == 1
    assert selected[0]["session"] == newer_low["session"]
    assert ambiguous == []


def test_equal_timestamp_is_ambiguous_and_score_is_hidden():
    first = sidecar("aaa", "2026-01-01T00:00:00+00:00")
    second = sidecar("zzz", "2026-01-01T00:00:00+00:00")
    selected, ambiguous = select_representatives([first, second])
    assert selected == []
    assert len(ambiguous) == 1
    markdown, _ = render_markdown([first, second], [])
    assert "100.00%" not in markdown


def test_mixed_dated_and_undated_candidates_are_ambiguous():
    dated = sidecar("dated", "2026-01-01T00:00:00+00:00")
    undated = sidecar("undated", None)
    selected, ambiguous = select_representatives([dated, undated])
    assert selected == []
    assert len(ambiguous) == 1
    assert "섞여 있음" in ambiguous[0]["reason"]


def test_rejected_scores_never_render_and_unscored_alone_is_not_strict_failure():
    rejected = sidecar("polluted", None, status="REJECTED", score=1)
    rejected["metrics"]["axes"] = [{"name": "overall", "value": 24.41, "unit": "score/10"}]
    markdown, ambiguous = render_markdown([rejected], [])
    assert "24.41" not in markdown
    unscored = sidecar(
        "generation", None, status="UNSCORED", score=0,
        benchmark="KOFFVQA", variant="generation",
    )
    assert strict_failed([unscored], [], []) is False
    wrong_unscored = sidecar(
        "generation", None, status="UNSCORED", score=0,
        benchmark="KRETA", variant="direct",
    )
    assert strict_failed([wrong_unscored], [], []) is True
    assert strict_failed([rejected], [], ambiguous) is True


def test_headline_excludes_latency_and_detail_axes():
    accuracy = sidecar(
        "accuracy",
        "2026-01-01T00:00:00+00:00",
        benchmark="KRETA",
        variant="direct",
        axes=[
            {"name": "overall", "numerator": 8, "denominator": 10, "value": 0.8, "unit": "fraction"},
            {"name": "category:document", "numerator": 4, "denominator": 5, "value": 0.8, "unit": "fraction"},
        ],
    )
    latency = sidecar(
        "latency",
        "2026-01-01T00:00:00+00:00",
        benchmark="B4-latency-profile",
        variant="latency",
        axes=[
            {"name": "text_only:ttft:p50", "value": 0.1, "unit": "seconds"},
            {"name": "text_only:ttft:p95", "value": 0.2, "unit": "seconds"},
            {"name": "text_only:ttft:p99", "value": 0.3, "unit": "seconds"},
        ],
    )
    markdown, _ = render_markdown([accuracy, latency], [])
    headline = markdown.split("## 헤드라인", 1)[1].split("## 상태 요약", 1)[0]
    assert "B4-latency-profile" not in headline
    assert "category:" not in headline
    assert ":p95" not in headline
    assert ":p99" not in headline
    assert markdown.rfind("## B4 지연시간") > markdown.find("## 세부 축")


def test_different_fingerprints_render_in_separate_headline_tables():
    first = sidecar(
        "first",
        "2026-01-01T00:00:00+00:00",
        benchmark="KRETA",
        variant="direct",
        model="model-alpha",
        item_digest="item-set-a",
        score=1,
    )
    second = sidecar(
        "second",
        "2026-01-01T00:00:00+00:00",
        benchmark="KRETA",
        variant="direct",
        model="model-beta",
        item_digest="item-set-b",
        score=0,
    )
    markdown, _ = render_markdown([first, second], [])
    headline = markdown.split("## 헤드라인", 1)[1].split("## 상태 요약", 1)[0]
    table_blocks = [block for block in headline.split("### ") if "| 모델 | 결과 | 무답률 | 상태 |" in block]
    assert len(table_blocks) == 2
    assert all(not ("model-alpha" in block and "model-beta" in block) for block in table_blocks)


def test_headline_sorts_models_by_result_descending_within_cohort():
    lower = sidecar(
        "lower",
        "2026-01-01T00:00:00+00:00",
        benchmark="K-DTCBench",
        model="aaa-lower",
        score=0,
    )
    higher = sidecar(
        "higher",
        "2026-01-01T00:00:00+00:00",
        benchmark="K-DTCBench",
        model="zzz-higher",
        score=1,
    )
    markdown, _ = render_markdown([lower, higher], [])
    headline = markdown.split("## 헤드라인", 1)[1].split("## 상태 요약", 1)[0]
    assert headline.index("zzz-higher") < headline.index("aaa-lower")


def test_headline_notes_different_repo_commits_in_same_item_cohort():
    first = sidecar(
        "first",
        "2026-01-01T00:00:00+00:00",
        benchmark="KRETA",
        model="model-alpha",
        dataset_commit="a" * 40,
    )
    second = sidecar(
        "second",
        "2026-01-01T00:00:00+00:00",
        benchmark="KRETA",
        model="model-beta",
        dataset_commit="b" * 40,
    )
    markdown, _ = render_markdown([first, second], [])
    assert "기록된 repo commit이 런마다 다름(문항 집합은 동일)" in markdown


def test_kreta_headline_shows_no_answer_column_and_quality_notes():
    result = sidecar(
        "run", "2026-01-01T00:00:00+00:00",
        benchmark="KRETA", variant="direct", no_answer=21,
        parser_disagreement=23,
    )
    markdown, _ = render_markdown([result], [])
    headline = markdown.split("## 헤드라인", 1)[1].split("## 상태 요약", 1)[0]
    assert "| 모델 | 결과 | 무답률 | 상태 |" in headline
    assert "21.0%" in headline
    assert "상류 parser와 23행 불일치(우리 무답 21, 다른 선택지 2)" in headline
    assert "점수를 능력 차이로만 해석하지 말 것" in headline


def test_commit_note_uses_all_candidates_before_representative_selection():
    older = sidecar(
        "older",
        "2026-01-01T00:00:00+00:00",
        benchmark="KRETA",
        dataset_commit="a" * 40,
    )
    newer = sidecar(
        "newer",
        "2026-01-02T00:00:00+00:00",
        benchmark="KRETA",
        dataset_commit="b" * 40,
    )
    markdown, _ = render_markdown([older, newer], [])
    assert "기록된 repo commit이 런마다 다름(문항 집합은 동일)" in markdown


def test_identical_artifact_sha_folds_copied_run_with_path_priority():
    bad = sidecar(
        "same", "2026-01-01T00:00:00+00:00",
        source="results/model.bad/same/bench", artifact_sha="sha256:same",
    )
    canonical = sidecar(
        "same", "2026-01-01T00:00:00+00:00",
        source="results/model/same/bench", artifact_sha="sha256:same",
    )
    selected, ambiguous = select_representatives([bad, canonical])
    assert ambiguous == []
    assert selected[0]["source"]["unit"] == "results/model/same/bench"
    assert selected[0]["_selection"]["folded_duplicates"][0]["folded"] == [
        "results/model.bad/same/bench"
    ]
    markdown, _ = render_markdown([bad, canonical], [])
    assert "동일 artifact role/SHA-256·측정 payload 복사본" in markdown


def test_identical_artifacts_with_different_measurement_payload_do_not_fold():
    legacy = sidecar(
        "same", "2026-01-01T00:00:00+00:00", status="LEGACY_REVALIDATED",
        source="results/short/same/bench", artifact_sha="sha256:same", score=1,
    )
    native = sidecar(
        "same", "2026-01-01T00:00:00+00:00", status="NATIVE",
        source="results/much-longer-native/same/bench", artifact_sha="sha256:same", score=0,
    )
    selected, ambiguous = select_representatives([legacy, native])
    assert selected == []
    assert len(ambiguous) == 1
    assert {item["status"] for item in ambiguous[0]["candidates"]} == {
        "LEGACY_REVALIDATED", "NATIVE",
    }


def test_identical_payload_prefers_native_before_copy_path_priority():
    legacy = sidecar(
        "same", "2026-01-01T00:00:00+00:00", status="LEGACY_REVALIDATED",
        source="results/short/same/bench", artifact_sha="sha256:same",
    )
    native = sidecar(
        "same", "2026-01-01T00:00:00+00:00", status="NATIVE",
        source="results/model.bad/much-longer/same/bench", artifact_sha="sha256:same",
    )
    selected, ambiguous = select_representatives([legacy, native])
    assert ambiguous == []
    assert selected[0]["status"] == "NATIVE"
    assert selected[0]["source"]["unit"] == native["source"]["unit"]


def test_same_artifact_and_payload_from_different_sessions_is_not_folded():
    first = sidecar(
        "session-a", "2026-01-01T00:00:00+00:00",
        source="results/model/session-a/bench", artifact_sha="sha256:same",
    )
    second = sidecar(
        "session-b", "2026-01-02T00:00:00+00:00",
        source="results/model/session-b/bench", artifact_sha="sha256:same",
    )
    selected, ambiguous = select_representatives([first, second])
    assert ambiguous == []
    assert selected[0]["session"] == "session-b"
    assert len(selected[0]["_selection"]["cohort_runs"]) == 2
    assert selected[0]["_selection"]["folded_duplicates"] == []


def test_bad_session_suffix_is_the_only_session_copy_normalization():
    original = sidecar(
        "same", "2026-01-01T00:00:00+00:00",
        source="results/model/same/bench", artifact_sha="sha256:same",
    )
    copied = sidecar(
        "same.bad", "2026-01-01T00:00:00+00:00",
        source="results/model/same.bad/bench", artifact_sha="sha256:same",
    )
    selected, ambiguous = select_representatives([original, copied])
    assert ambiguous == []
    assert len(selected[0]["_selection"]["folded_duplicates"]) == 1


def test_artifact_roles_are_part_of_exact_copy_signature():
    first = sidecar(
        "same", "2026-01-01T00:00:00+00:00", source="results/a/same/bench",
        artifacts=[
            {"path": "results/a/same/bench/results.json", "sha256": "sha256:one"},
            {"path": "results/a/same/bench/summary.json", "sha256": "sha256:two"},
        ],
    )
    swapped = sidecar(
        "same", "2026-01-01T00:00:00+00:00", source="results/b/same/bench",
        artifacts=[
            {"path": "results/b/same/bench/results.json", "sha256": "sha256:two"},
            {"path": "results/b/same/bench/summary.json", "sha256": "sha256:one"},
        ],
    )
    selected, ambiguous = select_representatives([first, swapped])
    assert selected == []
    assert len(ambiguous) == 1


def test_different_artifact_sha_never_folds_equal_timestamp_runs():
    first = sidecar(
        "same", "2026-01-01T00:00:00+00:00", artifact_sha="sha256:first",
    )
    second = sidecar(
        "same", "2026-01-01T00:00:00+00:00", artifact_sha="sha256:second",
        source="results/other/same/bench",
    )
    selected, ambiguous = select_representatives([first, second])
    assert selected == []
    assert len(ambiguous) == 1


def test_unmapped_model_identity_warns_without_guessing():
    unknown = sidecar(
        "run", "2026-01-01T00:00:00+00:00",
        model="unknown-serving-name", canonical_model="unknown-serving-name",
        identity_mapped=False,
    )
    markdown, _ = render_markdown([unknown], [])
    assert "모델 정체성 경고" in markdown
    assert "추측해서 합치지 않고 자기 이름을 canonical id로 사용" in markdown


def test_fp8_identity_stays_separate_from_non_fp8():
    normal = sidecar(
        "normal", "2026-01-01T00:00:00+00:00",
        model="qwen", canonical_model="qwen",
    )
    fp8 = sidecar(
        "fp8", "2026-01-01T00:00:00+00:00",
        model="qwen_fp8", canonical_model="qwen_fp8",
    )
    selected, ambiguous = select_representatives([normal, fp8])
    assert ambiguous == []
    assert {item["model_identity"]["canonical_id"] for item in selected} == {"qwen", "qwen_fp8"}


def test_reproducibility_tolerance_boundary_and_strict_failure():
    def measured(session, timestamp, numerator, artifact_sha):
        return sidecar(
            session, timestamp, benchmark="K-DTCBench",
            model="serving-alias", canonical_model="canonical-model",
            artifact_sha=artifact_sha,
            axes=[{
                "name": "overall", "numerator": numerator, "denominator": 240,
                "value": numerator / 240, "unit": "fraction",
            }],
        )

    baseline = measured("baseline", "2026-01-01T00:00:00+00:00", 200, "sha256:base")
    boundary = measured("boundary", "2026-01-02T00:00:00+00:00", 203, "sha256:boundary")
    selected, ambiguous = select_representatives([baseline, boundary])
    assert strict_failed([boundary], [], [], [baseline, boundary]) is False
    markdown, _ = render_markdown([baseline, boundary], [])
    assert "코호트 산포 3건 (1.25%p), 허용 3건 — **PASS**" in markdown
    assert "`baseline`  200/240 = 83.33% (기준)" in markdown
    assert "`boundary`  203/240 = 84.58% (대표)" in markdown

    outside = measured("outside", "2026-01-03T00:00:00+00:00", 204, "sha256:outside")
    assert strict_failed([outside], [], [], [baseline, outside]) is True


def test_reproducibility_uses_full_cohort_spread_for_three_runs():
    def measured(session, timestamp, numerator):
        return sidecar(
            session, timestamp, benchmark="K-DTCBench",
            artifact_sha=f"sha256:{session}",
            axes=[{
                "name": "overall", "numerator": numerator, "denominator": 240,
                "value": numerator / 240, "unit": "fraction",
            }],
        )

    baseline = measured("baseline", "2026-01-01T00:00:00+00:00", 100)
    low = measured("low", "2026-01-02T00:00:00+00:00", 97)
    high = measured("high", "2026-01-03T00:00:00+00:00", 103)
    assert strict_failed([high], [], [], [baseline, low, high]) is True
    markdown, _ = render_markdown([baseline, low, high], [])
    assert "코호트 산포 6건 (2.50%p), 허용 3건 — **FAIL**" in markdown


def test_missing_or_unsupported_repro_axis_is_not_comparable_failure():
    missing = sidecar(
        "missing", "2026-01-01T00:00:00+00:00", artifact_sha="sha256:missing",
        axes=[{"name": "category:x", "numerator": 1, "denominator": 1, "value": 1.0, "unit": "fraction"}],
    )
    unsupported = sidecar(
        "unsupported", "2026-01-02T00:00:00+00:00", artifact_sha="sha256:unsupported",
        axes=[{"name": "overall", "value": 1.2, "unit": "seconds"}],
    )
    assert strict_failed([unsupported], [], [], [missing, unsupported]) is True
    markdown, _ = render_markdown([missing, unsupported], [])
    assert "비교 불가 — **FAIL**" in markdown
    assert "overall/rubric 비교 축이 없음" in markdown


def test_score_over_ten_uses_average_scale_not_score_sum_counts():
    def judged(session, timestamp, average, artifact_sha):
        return sidecar(
            session, timestamp, benchmark="KOFFVQA-judge", variant="api_judge",
            artifact_sha=artifact_sha, provisional=True,
            axes=[{
                "name": "rubric", "value": average, "unit": "score/10",
                "numerator": average * 275, "denominator": 275,
            }],
        )

    baseline = judged("baseline", "2026-01-01T00:00:00+00:00", 5.00, "sha256:base")
    close = judged("close", "2026-01-02T00:00:00+00:00", 5.02, "sha256:close")
    assert strict_failed([close], [], [], [baseline, close]) is False
    markdown, _ = render_markdown([baseline, close], [])
    assert "평균 점수 산포 0.020/10 (전체 척도 0.20%p), 허용 0.10/10 — **PASS**" in markdown

    far = judged("far", "2026-01-03T00:00:00+00:00", 5.11, "sha256:far")
    assert strict_failed([far], [], [], [baseline, far]) is True


def test_scoped_report_renders_comparison_failure_that_causes_strict_exit():
    baseline = sidecar(
        "baseline", "2026-01-01T00:00:00+00:00", benchmark="K-DTCBench",
        artifact_sha="sha256:base",
        axes=[{"name": "overall", "numerator": 200, "denominator": 240, "value": 200 / 240, "unit": "fraction"}],
    )
    current = sidecar(
        "current", "2026-01-02T00:00:00+00:00", benchmark="K-DTCBench",
        artifact_sha="sha256:current",
        axes=[{"name": "overall", "numerator": 190, "denominator": 240, "value": 190 / 240, "unit": "fraction"}],
    )
    markdown, ambiguous = render_markdown([current], [], [baseline, current])
    assert "코호트 산포 10건 (4.17%p), 허용 3건 — **FAIL**" in markdown
    assert strict_failed([current], [], ambiguous, [baseline, current]) is True


def test_b4_is_explicitly_excluded_from_reproducibility_strict_check():
    first = sidecar(
        "first", "2026-01-01T00:00:00+00:00", benchmark="B4-latency-profile",
        artifact_sha="sha256:first",
        axes=[{"name": "text_only:ttft:p50", "value": 0.1, "unit": "seconds"}],
    )
    second = sidecar(
        "second", "2026-01-02T00:00:00+00:00", benchmark="B4-latency-profile",
        artifact_sha="sha256:second",
        axes=[{"name": "text_only:ttft:p50", "value": 9.9, "unit": "seconds"}],
    )
    assert strict_failed([second], [], [], [first, second]) is False
