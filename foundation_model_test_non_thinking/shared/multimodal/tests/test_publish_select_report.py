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
):
    publishable = status in {"LEGACY_REVALIDATED", "NATIVE"}
    value = {
        "schema_version": 1,
        "benchmark_id": benchmark,
        "benchmark_key": benchmark,
        "variant": variant,
        "model": model,
        "session": session,
        "source": {"unit": source or f"results/model/{session}/bench", "artifacts": []},
        "status": status,
        "publishable": publishable,
        "provisional": False,
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
    assert selected == [newer_low]
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
    unscored = sidecar("generation", None, status="UNSCORED", score=0)
    assert strict_failed([unscored], [], []) is False
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
