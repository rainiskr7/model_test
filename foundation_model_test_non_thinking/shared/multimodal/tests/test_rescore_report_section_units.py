"""입력: 합성 반복 평균·출처. 출력: 새 절의 지표명·차이·평균·거부 표시 검증."""

from copy import deepcopy

from shared.multimodal.rescore.report_section import NOTICE, render_section


def test_empty_and_rejected_without_numeric_publication():
    text = render_section([], [{"model": "bad", "cohort": ["K-MMBench", "full", "fp"], "reason": "invalid"}])
    assert NOTICE in text and "표시 가능한 재채점 코호트가 없습니다." in text
    assert "재채점 제외: bad" in text and "invalid" in text
    assert "nan" not in text and "0.0000" not in text


def test_same_repeat_means_difference_units_and_provenance():
    value = {"model": "a|b", "metric": "kmmbench_circular_stored_judgement",
             "cohort": ["K-MMBench", "full", "sha256:fp"], "repetitions": 2,
             "old_mean": 0.9, "new_mean": 0.75, "representative": "results/a/r2/k_mmbench",
             "runs": [{"source": "results/a/r1/k_mmbench", "revision": "rev"},
                      {"source": "results/a/r2/k_mmbench", "revision": "rev"}],
             "upstream": {"repository": "https://example.org/repo", "commit": "sha", "path": "score.py"}}
    before = deepcopy(value)
    text = render_section([value])
    assert "| a\\|b |" in text and "| 2 | 90.0000 | 75.0000 | -15.0000 |" in text
    assert "같은 반복 집합의 평균" in text
    assert "대표: `results/a/r2/k_mmbench`" in text
    assert "반복: `results/a/r1/k_mmbench`" in text
    assert "https://example.org/repo/blob/sha/score.py" in text
    assert value == before and text.endswith("\n")
