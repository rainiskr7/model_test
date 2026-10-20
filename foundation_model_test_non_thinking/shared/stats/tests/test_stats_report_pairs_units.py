"""입력: 합성 paired 코호트·검증 오류. 출력: CLI 계산 재사용·거부와 구현 오류 구별 검증."""

from copy import deepcopy

import pytest

from shared.stats.report_pairs import compare_pairs, render_pairs
from shared.stats.selection import SelectionError
from shared.stats.tests.test_stats_main_units import enriched_pair


def test_empty_pairs_and_missing_scope_are_visible():
    assert "선언된 비교 쌍이 없습니다." in render_pairs(compare_pairs([], {}))
    values = compare_pairs([{"a": "a", "b": "b", "bench": "k_dtcbench"}], {})
    assert "범위 내 발행 가능 코호트 없음" in values[0]["error"]
    assert "비교 불가:" in render_pairs(values)


def test_exact_cli_comparison_and_nonmutation():
    a, b = enriched_pair()
    pairs = [{"a": "a", "b": "b", "bench": "k_dtcbench"}]
    cohorts = {("a", "k_dtcbench"): a, ("b", "k_dtcbench"): b}
    before = deepcopy((pairs, cohorts))
    values = compare_pairs(pairs, cohorts, seed=42, resamples=100)
    r = values[0]["result"]
    assert r["difference"] == 1 / 3 and r["ci95"] == [-1, 1]
    text = render_pairs(values)
    assert "+33.3333" in text and "[-100.0000, +100.0000]" in text
    assert "관측한 반복 평균에 조건부인 문항 표집 불확실성" in text
    assert "seed=42, resamples=100" in text and "A: `results/a/session/bench`" in text
    assert (pairs, cohorts) == before


def test_selection_rejection_is_reported_but_implementation_errors_propagate(monkeypatch):
    pair = [{"a": "a", "b": "b", "bench": "k_dtcbench"}]
    cohorts = {("a", "k_dtcbench"): SelectionError("rejected fixture")}
    assert compare_pairs(pair, cohorts)[0]["error"] == "rejected fixture"
    a, b = enriched_pair()
    cohorts = {("a", "k_dtcbench"): a, ("b", "k_dtcbench"): b}
    def fail(*args, **kwargs):
        raise RuntimeError("implementation failure")
    monkeypatch.setattr("shared.stats.report_pairs.comparison", fail)
    with pytest.raises(RuntimeError, match="implementation"):
        compare_pairs(pair, cohorts)
