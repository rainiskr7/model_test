"""무엇: 비교 공개 투영 · 입력: 비교 schema · 출력: 분모 구분과 명시 연결 · 계약 §7-6."""

import pytest

from jeveval.score.report_extras import comparison


def test_comparison_labels_different_populations_and_rejects_models():
    pairs = dict(pairs=[dict(models=["a", "b"], estimate=.1, ci95=[0, .2])])
    value = dict(schema="compare/1", models=["a", "b"], set="s", variant="v",
                 bootstrap=dict(coverage={"0.02": pairs}, f1={"test": {"q": pairs}}))
    result = comparison(value, "explicit", ["a", "b"], "s", "v")
    assert "전체 test 대표" in result.lines[0] and "공통 ok" in result.lines[1]
    with pytest.raises(ValueError):
        comparison(value, "explicit", ["a", "c"], "s", "v")
